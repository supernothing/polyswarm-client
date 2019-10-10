import aioredis
import datetime
import logging

from polyswarmclient.ratelimit.abstractratelimit import AbstractRateLimit

logger = logging.getLogger(__name__)


class RedisDailyRateLimit(AbstractRateLimit):
    """ Third Party limitation where redis is used to track a daily scan limit.
        Keys are based on the current date, and will expire the next day.

        This implemntation is used in the worker since it is known to use Redis.
    """
    def __init__(self, redis_uri, queue, limit):
        self.redis_uri = redis_uri
        self.redis = None
        self.queue = queue
        self.limit = limit if limit is None else int(limit)

    def get_daily_key(self):
        date = datetime.date.today().strftime('%Y-%m-%d')
        return f'{self.queue}:{date}'

    async def setup(self):
        self.redis = await aioredis.create_redis_pool(self.redis_uri)

    async def use(self, *args, **kwargs):
        """
        Keep track of use by incrementing a counter for the current date

        Args:
            *args: None
            **kwargs: None
        """
        if self.limit is None:
            return True

        key = self.get_daily_key()
        value = await self.redis.incr(key)
        if value == 1:
            # Give an hour extra before expiring, in case someone wants to take a look manually
            await self.redis.expire(key, 60 * 60 * 25)

        if value <= self.limit:
            return True
        else:
            logger.warning("Reached daily limit of %s with %s total attempts", self.limit, value)
            return False
