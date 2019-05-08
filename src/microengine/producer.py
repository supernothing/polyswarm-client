import aioredis
import asyncio
import json
import logging
import os
import time

from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import ScanResult

logger = logging.getLogger(__name__)

REDIS_ADDR = os.getenv('REDIS_ADDR', 'localhost:6379')
QUEUE = os.getenv('QUEUE')

TIME_TO_POST_ASSERTION = 4
KEY_TIMEOUT = 20


class Microengine(AbstractMicroengine):
    def __init__(self, client, testing=0, scanner=None, chains=None):
        super().__init__(client, testing, None, chains)

        if QUEUE is None:
            raise ValueError('No queue configured, set the QUEUE environment variable')
        if QUEUE.endswith('_results'):
            raise ValueError('Queue name cannot end with "_results"')

        self.client.on_run.register(self.__handle_run)
        self.redis = None

    async def __handle_run(self, chain):
        if self.redis is None:
            redis_uri = 'redis://' + REDIS_ADDR
            self.redis = await aioredis.create_redis_pool(redis_uri)

    async def fetch_and_scan_all(self, guid, uri, duration, chain):
        """Overrides the default fetch logic to embed the URI and index rather than downloading on producer side

        Args:
            guid (str): GUID of the associated bounty
            uri (str):  Base artifact URI
            duration (int): Blocks until bounty expiration
            chain (str): Chain we are operating on

        Returns:
            (list(bool), list(bool), list(str)): Tuple of mask bits, verdicts, and metadatas
        """

        # Ensure we don't wait past the bounty duration for one long artifact
        timeout = duration - TIME_TO_POST_ASSERTION

        async def wait_for_result(key):
            try:
                with await self.redis as redis:
                    result = await redis.blpop(key, timeout=timeout)
                    if result is None:
                        logger.critical('Timeout waiting for result in bounty %s', guid)
                        return None

                    j = json.loads(result[1].decode('utf-8'))
                    return j['index'], ScanResult(bit=j['bit'], verdict=j['verdict'], confidence=j['confidence'],
                                                  metadata=j['metadata'])
            except aioredis.errors.ReplyError:
                logger.exception('Redis out of memory')
            except OSError:
                logger.exception('Redis connection down')
            except (AttributeError, ValueError, KeyError):
                logger.error('Received invalid response from worker')
                return None

        num_artifacts = len(await self.client.list_artifacts(uri))
        jobs = [json.dumps({
            'ts': time.time() // 1,
            'guid': guid,
            'uri': uri,
            'index': i,
            'chain': chain,
            'duration': timeout,
            'polyswarmd_uri': self.client.polyswarmd_uri}) for i in range(num_artifacts)]

        try:
            await self.redis.rpush(QUEUE, *jobs)

            key = '{}_{}_{}_results'.format(QUEUE, guid, chain)
            results = await asyncio.gather(*[wait_for_result(key) for _ in jobs])
            results = {r[0]: r[1] for r in results if r is not None}

            # Age off old result keys
            await self.redis.expire(key, KEY_TIMEOUT)

            return [results.get(i, ScanResult()) for i in range(num_artifacts)]
        except OSError:
            logger.exception('Redis connection down')
        except aioredis.errors.ReplyError:
            logger.exception('Redis out of memory')

        return []
