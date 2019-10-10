import aioredis
import asyncio
import json
import logging
import time

from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.filters.filter import MetadataFilter

logger = logging.getLogger(__name__)

WAIT_TIME = 20
KEY_TIMEOUT = WAIT_TIME + 10


class Producer:
    def __init__(self, client, redis_uri, queue, time_to_post, bounty_filter=None, confidence_modifier=None,
                 rate_limit=None):
        self.client = client
        self.redis_uri = redis_uri
        self.queue = queue
        self.time_to_post = time_to_post
        self.bounty_filter = bounty_filter
        self.confidence_modifier = confidence_modifier
        self.redis = None
        self.rate_limit = rate_limit

    async def start(self):
        if self.rate_limit is not None:
            await self.rate_limit.setup()
        self.redis = await aioredis.create_redis_pool(self.redis_uri)

    async def scan(self, guid, artifact_type, uri, expiration_blocks, metadata, chain):
        """Creates a set of jobs to scan all the artifacts at the given URI that are passed via Redis to workers

            Args:
                guid (str): GUID of the associated bounty
                artifact_type (ArtifactType): Artifact type for the bounty being scanned
                uri (str):  Base artifact URI
                expiration_blocks (int): Blocks until vote round ends
                metadata (list[dict]) List of metadata json blobs for artifacts
                chain (str): Chain we are operating on

            Returns:
                list(ScanResult): List of ScanResult objects
            """
        # Ensure we don't wait past the vote round duration for one long artifact
        timeout = expiration_blocks - self.time_to_post
        logger.info(f' timeout set to {timeout}')

        async def wait_for_result(result_key):
            try:
                with await self.redis as redis:
                    while True:
                        result = await redis.lpop(result_key)

                        if result:
                            break

                        await asyncio.sleep(1)

                    j = json.loads(result.decode('utf-8'))

                    # increase perf counter for autoscaling
                    q_counter = f'{self.queue}_scan_result_counter'
                    await redis.incr(q_counter)
                    confidence = j['confidence'] if not self.confidence_modifier \
                        else self.confidence_modifier.modify(metadata[j['index']], j['confidence'])

                    return j['index'], ScanResult(bit=j['bit'], verdict=j['verdict'], confidence=confidence,
                                                  metadata=j['metadata'])
            except aioredis.errors.ReplyError:
                logger.exception('Redis out of memory')
            except OSError:
                logger.exception('Redis connection down')
            except (AttributeError, ValueError, KeyError):
                logger.exception('Received invalid response from worker')
                return None

        num_artifacts = len(await self.client.list_artifacts(uri))
        # Fill out metadata to match same number of artifacts
        metadata = MetadataFilter.pad_metadata(metadata, num_artifacts)

        jobs = []
        for i in range(num_artifacts):
            if (self.bounty_filter is None or self.bounty_filter.is_allowed(metadata[i])) \
             and (self.rate_limit is None or await self.rate_limit.use()):
                jobs.append(json.dumps({
                    'ts': time.time() // 1,
                    'guid': guid,
                    'artifact_type': artifact_type.value,
                    'uri': uri,
                    'index': i,
                    'chain': chain,
                    'duration': timeout,
                    'polyswarmd_uri': self.client.polyswarmd_uri,
                    'metadata': metadata[i]}
                ))

        if jobs:
            try:
                await self.redis.rpush(self.queue, *jobs)

                key = '{}_{}_{}_results'.format(self.queue, guid, chain)
                results = await asyncio.gather(*[asyncio.wait_for(wait_for_result(key), timeout=timeout) for _ in jobs],
                                               return_exceptions=True)
                # In the event of filter or rate limit, the index (r[0]) will not have a value in the dict
                results = {r[0]: r[1] for r in results if r is not None and not isinstance(r, asyncio.TimeoutError)}
                if len(results.keys()) < num_artifacts:
                    logger.error('Timeout handling guid %s', guid)

                # Age off old result keys
                await self.redis.expire(key, KEY_TIMEOUT)

                # Any missing responses will be replaced inline with an empty scan result
                return [results.get(i, ScanResult()) for i in range(num_artifacts)]
            except OSError:
                logger.exception('Redis connection down')
            except aioredis.errors.ReplyError:
                logger.exception('Redis out of memory')

        return []
