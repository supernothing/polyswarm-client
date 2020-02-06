import aioredis
import aiohttp
import asyncio
import json
import logging
import math
import platform
import signal
import time

import backoff
from aiohttp import ClientSession
from typing import AsyncGenerator

from aioredis import Redis
from polyswarmartifact import DecodeError
from polyswarmclient.liveness.local import LocalLivenessRecorder
from polyswarmclient.exceptions import ApiKeyException
from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.producer import JobResponse, JobRequest
from polyswarmclient.utils import asyncio_join, asyncio_stop, exit, MAX_WAIT, configure_event_loop
from worker.exceptions import EmptyJobsQueueException, ExpiredException

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 5.0


class OptionalSemaphore(asyncio.Semaphore):
    given_value: int

    def __init__(self, value=1, loop=None):
        self.given_value = value
        try:
            super().__init__(value=value, loop=loop)
        except ValueError:
            # We have handling for values < 1, so we can ignore this value error
            pass

    async def acquire(self):
        if self.given_value > 0:
            await super().acquire()

        return True

    def release(self) -> None:
        if self.given_value > 0:
            super().release()


class Worker:
    def __init__(self, redis_addr, queue, task_count=0, download_limit=0, scan_limit=0, api_key=None, testing=0,
                 scanner=None):
        self.redis_uri = 'redis://' + redis_addr
        self.redis = None
        self.queue = queue
        self.api_key = api_key
        self.testing = testing
        self.scanner = scanner
        self.task_count = task_count
        self.download_limit = download_limit
        self.scan_limit = scan_limit
        self.download_semaphore = None
        self.scan_semaphore = None
        self.job_semaphore = None
        self.tries = 0
        self.finished = False
        # Setup a liveness instance
        self.liveness_recorder = LocalLivenessRecorder()

    def run(self):
        while not self.finished:
            configure_event_loop()
            loop = asyncio.get_event_loop()
            try:
                self.start(loop)
                # This stops any leftover tasks after out main task finishes
                asyncio_stop()
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

    def start(self, loop: asyncio.AbstractEventLoop):
        loop.run_until_complete(self.setup(loop))
        loop.run_until_complete(self.run_task())

    async def setup(self, loop: asyncio.AbstractEventLoop):
        self.setup_semaphores(loop)
        self.setup_graceful_shutdown(loop)
        await self.setup_liveness(loop)
        await self.setup_redis()
        if not await self.scanner.setup():
            logger.critical('Scanner instance reported unsuccessful setup. Exiting.')
            exit(1)

    def setup_semaphores(self, loop: asyncio.AbstractEventLoop):
        self.scan_semaphore = OptionalSemaphore(value=self.scan_limit, loop=loop)
        self.download_semaphore = OptionalSemaphore(value=self.download_limit, loop=loop)
        self.job_semaphore = OptionalSemaphore(value=self.task_count, loop=loop)

    def setup_graceful_shutdown(self, loop: asyncio.AbstractEventLoop):
        # K8 uses SIGTERM on linux and SIGINT and windows
        exit_signal = signal.SIGINT if platform.system() == 'Windows' else signal.SIGTERM
        try:
            loop.add_signal_handler(exit_signal, self.handle_signal)
        except NotImplementedError:
            # Disable graceful exit, but run anyway
            logger.warning(f'{platform.system()} does not support graceful shutdown')

    def handle_signal(self):
        logger.critical(f'Received exit signal. Gracefully shutting down.')
        self.finished = True

    async def setup_liveness(self, loop: asyncio.AbstractEventLoop):
        async def advance_liveness_time(liveness):
            while True:
                await liveness.advance_time(round(time.time()))
                await asyncio.sleep(1)

        await self.liveness_recorder.start()
        loop.create_task(advance_liveness_time(self.liveness_recorder))

    async def setup_redis(self):
        self.redis = await aioredis.create_redis_pool(self.redis_uri)

    async def run_task(self):
        loop = asyncio.get_event_loop()
        conn = aiohttp.TCPConnector(limit=0, limit_per_host=0)
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            while True:
                async for job in self.get_jobs():
                    loop.create_task(self.process_job(job, session))

    async def get_jobs(self) -> AsyncGenerator[JobRequest, None]:
        with await self.redis as redis:
            while not self.finished:
                # Lock sets up our task limit, the lock is released
                try:
                    await self.job_semaphore.acquire()
                    job = await redis.blpop(self.queue, timeout=1)
                    if not job:
                        raise EmptyJobsQueueException

                    _, job = job
                    job = json.loads(job.decode('utf-8'))
                    logger.info(f'Received job', extra={'extra': job})
                    yield JobRequest(**job)
                except OSError:
                    logger.exception('Redis connection down')
                    self.job_semaphore.release()
                except aioredis.errors.ReplyError:
                    logger.exception('Redis out of memory')
                    self.job_semaphore.release()
                except (TypeError, KeyError):
                    logger.exception('Invalid job received, ignoring')
                    self.job_semaphore.release()
                except EmptyJobsQueueException:
                    self.job_semaphore.release()
                except (OSError, aioredis.errors.ReplyError):
                    logger.exception('Error reading jobs from redis')
                    self.job_semaphore.release()
                    raise StopAsyncIteration

    async def process_job(self, job: JobRequest, session: ClientSession):
        remaining_time = 0
        try:
            await self.liveness_recorder.add_waiting_task(job.key, round(time.time()))
            remaining_time = self.get_remaining_time(job)
            content = await self.download(job, session)
            scan_result = await asyncio.wait_for(self.scan(job, content), timeout=remaining_time)
            response = JobResponse(job.index, scan_result.bit, scan_result.verdict, scan_result.confidence,
                                   scan_result.metadata)
            asyncio.get_event_loop().create_task(self.respond(job, response))
            self.tries = 0
        except OSError:
            logger.exception('Redis connection down')
        except aioredis.errors.ReplyError:
            logger.exception('Redis out of memory')
        except ExpiredException:
            logger.exception(f'Received expired job', extra={'extra': job.asdict()})
        except aiohttp.ClientResponseError:
            logger.exception(f'Error fetching artifact', extra={'extra': job.asdict()})
        except DecodeError:
            logger.exception('Error Decoding artifact', extra={'extra': job.asdict()})
        except ApiKeyException:
            logger.exception('Refusing to send API key over insecure transport')
        except asyncio.TimeoutError:
            logger.exception(f'Timeout processing artifact after %s seconds', remaining_time,
                             extra={'extra': job.asdict()})
        except asyncio.CancelledError:
            logger.exception(f'Worker shutdown while processing job', extra={'extra': job.asdict()})
        finally:
            await self.liveness_recorder.remove_waiting_task(job.key)
            self.job_semaphore.release()

    @staticmethod
    def get_remaining_time(job: JobRequest) -> int:
        remaining_time = int(job.ts + job.duration - math.floor(time.time()))
        if remaining_time < 0:
            raise ExpiredException()
        return remaining_time

    async def download(self, job: JobRequest, session: ClientSession) -> bytes:
        if self.api_key and not job.polyswarmd_uri.startswith('https://'):
            raise ApiKeyException()

        headers = {'Authorization': self.api_key} if self.api_key is not None else None
        uri = f'{job.polyswarmd_uri}/artifacts/{job.uri}/{job.index}'
        async with self.download_semaphore:
            response = await session.get(uri, headers=headers)
            response.raise_for_status()
            return await response.read()

    async def scan(self, job: JobRequest, content: bytes) -> ScanResult:
        artifact_type = job.get_artifact_type()
        async with self.scan_semaphore:
            return await self.scanner.scan(job.guid, artifact_type, artifact_type.decode_content(content), job.metadata,
                                           job.chain)

    async def respond(self, job: JobRequest, response: JobResponse):
        logger.info('Scan results for job %s', job.key, extra={'extra': response.asdict()})
        key = f'{self.queue}_{job.guid}_{job.chain}_results'
        json_response = json.dumps(response.asdict())
        with await self.redis as redis:
            await redis.rpush(key, json_response)
