import asyncio
from concurrent.futures import ThreadPoolExecutor


def run_in_executor(f):
    def inner(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(ThreadPoolExecutor(), lambda: f(*args, **kwargs))
    return inner
