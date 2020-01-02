import aioredis
import aiohttp
import asyncio
import json
import logging
import math
import platform
import signal
import sys
import time

from polyswarmartifact import ArtifactType, DecodeError
from polyswarmclient import LivelinessRecorder
from polyswarmclient.exceptions import ApiKeyException, ExpiredException
from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.utils import asyncio_join, asyncio_stop, exit, MAX_WAIT

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 5.0


class Worker(object):
    def __init__(self, redis_addr, queue, task_count=1, download_limit=1, scan_limit=1, api_key=None, testing=0,
                 scanner=None):
        self.redis_uri = 'redis://' + redis_addr
        self.queue = queue
        self.api_key = api_key
        self.testing = testing
        self.scanner = scanner
        self.task_count = task_count
        self.download_limit = download_limit
        self.scan_limit = scan_limit
        self.download_lock = None
        self.scan_lock = None
        self.tries = 0
        self.finished = False
        # Setup a liveliness instance
        self.liveliness_recorder = LivelinessRecorder()

    def handle_signal(self):
        logger.critical(f'Received SIGTERM. Gracefully shutting down.')
        self.finished = True

    def run(self):
        while not self.finished:
            loop = asyncio.SelectorEventLoop()

            # Default event loop does not support pipes on Windows
            if sys.platform == 'win32':
                loop = asyncio.ProactorEventLoop()

            asyncio.set_event_loop(loop)

            # K8 uses SIGTERM on linux and SIGINT and windows
            exit_signal = signal.SIGINT if platform.system() == 'Windows' else signal.SIGTERM
            try:
                loop.add_signal_handler(exit_signal, self.handle_signal)
            except NotImplementedError:
                # Disable graceful exit, but run anyway
                logger.warning(f'{platform.system()} does not support graceful shutdown')
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self.setup())
                loop.create_task(Worker.start_liveliness_recorder(self.liveliness_recorder))
                gather_task = asyncio.gather(*[self.run_task(i) for i in range(self.task_count)])
                loop.run_until_complete(gather_task)
            except asyncio.CancelledError:
                logger.info('Clean exit requested, exiting')

                asyncio_join()
                exit(0)
            except Exception:
                logger.exception('Unhandled exception at top level')
                asyncio_stop()
                asyncio_join()

                self.tries += 1
                wait = min(MAX_WAIT, self.tries * self.tries)

                logger.critical(f'Detected unhandled exception, sleeping for {wait} seconds then resetting task')
                time.sleep(wait)
                continue

    @staticmethod
    async def start_liveliness_recorder(liveliness_recorder):
        while True:
            await liveliness_recorder.advance_loop()
            # Worker
            await liveliness_recorder.advance_time(round(time.time()))
            await asyncio.sleep(1)

    async def setup(self):
        self.scan_lock = asyncio.Semaphore(value=self.scan_limit)
        self.download_lock = asyncio.Semaphore(value=self.download_limit)
        await self.liveliness_recorder.setup()
        if not await self.scanner.setup():
            logger.critical('Scanner instance reported unsuccessful setup. Exiting.')
            exit(1)

    async def download(self, polyswarmd_uri, uri, index, session):
        headers = {'Authorization': self.api_key} if self.api_key is not None else None
        uri = f'{polyswarmd_uri}/artifacts/{uri}/{index}'
        async with self.download_lock:
            response = await session.get(uri, headers=headers)
            response.raise_for_status()
            return await response.read()

    async def scan(self, guid, artifact_type, content, metadata, chain):
        async with self.scan_lock:
            return await self.scanner.scan(guid, artifact_type, artifact_type.decode_content(content), metadata, chain)

    async def run_task(self, task_index):
        conn = aiohttp.TCPConnector(limit=0, limit_per_host=0)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            redis = await aioredis.create_redis_pool(self.redis_uri)
            while not self.finished:
                try:
                    next_job = await redis.blpop(self.queue, timeout=1)
                    if next_job is None:
                        continue

                    _, job = next_job
                    job = json.loads(job.decode('utf-8'))
                    logger.info(f'Got job on task {task_index}', extra={'extra': job})

                    guid = job['guid']
                    uri = job['uri']
                    self.liveliness_recorder.add_waiting_task(guid, round(time.time()))

                    polyswarmd_uri = job['polyswarmd_uri']

                    if self.api_key and not polyswarmd_uri.startswith('https://'):
                        raise ApiKeyException()

                    index = job['index']
                    chain = job['chain']
                    metadata = job.get('metadata', None)

                    duration = job['duration']
                    timestamp = job['ts']
                    artifact_type = ArtifactType(int(job['artifact_type']))

                    if timestamp + duration <= math.floor(time.time()):
                        raise ExpiredException()

                except OSError:
                    logger.exception('Redis connection down')
                    self.liveliness_recorder.remove_waiting_task(guid)
                    continue
                except aioredis.errors.ReplyError:
                    logger.exception('Redis out of memory')
                    self.liveliness_recorder.remove_waiting_task(guid)
                    continue
                except KeyError as e:
                    logger.exception(f'Bad message format on task {task_index}: {e}')
                    self.liveliness_recorder.remove_waiting_task(guid)
                    continue
                except ExpiredException:
                    logger.exception(f'Received expired job {guid} index {index}')
                    self.liveliness_recorder.remove_waiting_task(guid)
                    continue
                except ApiKeyException:
                    logger.exception('Refusing to send API key over insecure transport')
                    self.liveliness_recorder.remove_waiting_task(guid)
                    continue
                except (AttributeError, TypeError, ValueError):
                    logger.exception('Invalid job received, ignoring')
                    self.liveliness_recorder.remove_waiting_task(guid)
                    continue

                remaining_time = int(timestamp + duration - time.time())
                # Setup default response as ScanResult, in case we exceeded uses
                result = ScanResult()
                try:
                    content = await self.download(polyswarmd_uri, uri, index, session)
                    result = await asyncio.wait_for(
                        self.scan(guid, artifact_type, content, metadata, chain),
                        timeout=remaining_time)
                except DecodeError:
                    logger.exception('Error Decoding artifact')
                except aiohttp.ClientResponseError:
                    logger.exception(f'Error fetching artifact {uri} on task {task_index}')
                except asyncio.TimeoutError:
                    logger.exception(f'Timeout processing artifact {uri} on task {task_index}')

                self.liveliness_recorder.remove_waiting_task(guid)

                j = json.dumps({
                    'index': index,
                    'bit': result.bit,
                    'verdict': result.verdict,
                    'confidence': result.confidence,
                    'metadata': result.metadata,
                })

                logger.info(f'Scan results on task {task_index}', extra={'extra': j})

                key = f'{self.queue}_{guid}_{chain}_results'
                try:
                    await redis.rpush(key, j)
                    self.tries = 0
                except OSError:
                    logger.exception('Redis connection down')
                except aioredis.errors.ReplyError:
                    logger.exception('Redis out of memory')
