import asyncio
import json
import logging
import platform


import jsonschema
import os
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger(__name__)


class Liveliness:
    """Liveliness object with status"""
    schema = {
        '$schema': 'http://json-schema.org/draft-07/schema#',
        '$id': 'liveliness.json',
        'type': 'object',
        'properties': {
            'latest_loop': {
                'type': 'number'
            },
            'average_wait': {
                'type': 'number',
            }
        },
        'additionalItems': True,
        'required': ['latest_loop', 'average_wait']
    }

    def __init__(self, last_iteration, avg_wait):
        self.last_iteration = last_iteration
        self.avg_wait = avg_wait

    @staticmethod
    def from_json(content):
        """
        Build a liveliness object from json
        Args:
            content: json string representing a liveliness object

        Returns:
            None if invalid JSON, or a Liveliness object
        """
        try:
            loaded = json.loads(content)
            jsonschema.validate(loaded, Liveliness.schema)
        except (json.JSONDecodeError, jsonschema.ValidationError):
            logger.exception('Unable to decode and validate json')
            return None

        return Liveliness(loaded['latest_loop'], loaded['average_wait'])

    def json(self):
        """Dump Liveliness object as json

        Returns:
            json string with Liveliness fields
        """
        return json.dumps({
            'latest_loop': self.last_iteration,
            'average_wait': self.avg_wait,
        })


class FileLock:
    """Locks a file so that only LivelinessRecorder or LivelinessChecker can access at any moment"""
    def __init__(self, fileno):
        self.fileno = fileno

    def acquire(self):
        if 'Windows' not in platform.system():
            self.acquire_unix()
        else:
            self.acquire_windows()

    def release(self):
        if 'Windows' not in platform.system():
            self.release_unix()

    # noinspection PyUnresolvedReferences
    def acquire_unix(self):
        from fcntl import lockf, LOCK_EX
        lockf(self.fileno, LOCK_EX)

    # noinspection PyUnresolvedReferences
    def acquire_windows(self):
        from msvcrt import locking, LK_LOCK
        locking(self.fileno, LK_LOCK, 1)

    # noinspection PyUnresolvedReferences
    def release_unix(self):
        from fcntl import lockf, LOCK_UN
        lockf(self.fileno, LOCK_UN)

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class LivelinessChecker:
    """Checks on the liveliness of a participant"""
    def __init__(self, loop_iteration_threshold=5, avg_wait_time_threshold=10):
        self.path = os.path.join(tempfile.gettempdir(), 'liveliness')
        self.loop_iteration_threshold = loop_iteration_threshold
        self.avg_wait_time_threshold = avg_wait_time_threshold

    def check(self):
        """Determine if participant is running smoothly, based on given inputs"""
        if not os.path.exists(self.path) or not os.path.isfile(self.path):
            return False

        with open(self.path, 'r+') as f:
            try:
                with FileLock(f.fileno()):
                    content = f.read()
                    logger.debug('Liveliness contents %s', content)
                    liveliness = Liveliness.from_json(content)
            except OSError:
                logger.exception('Unable to lock file')
                return False

        if liveliness is None:
            print('No liveliness information available')
            return False

        time_since_last_loop = int(time.time()) - liveliness.last_iteration
        print('Last loop was {0} seconds ago, and the average wait time is {1}'.format(time_since_last_loop,
                                                                                       liveliness.avg_wait))
        return time_since_last_loop < self.loop_iteration_threshold and \
            liveliness.avg_wait < self.avg_wait_time_threshold


class LivelinessRecorder:
    """Class that tracks the liveliness of some participant.
    Includes utilities to write the current state to a file that is shared with a liveliness checker
    """
    def __init__(self):
        self.path = os.path.join(tempfile.gettempdir(), 'liveliness')
        self.thread_pool_executor = ThreadPoolExecutor()
        self.waiting = []
        self.block_number = 0
        self.liveliness = Liveliness(0, 0)
        self.update_lock = None

    async def setup(self):
        self.update_lock = asyncio.Lock()

    async def advance_loop(self):
        """The loop is turning, and record the time of the latest iteration"""
        async with self.update_lock:
            self.liveliness.last_iteration = round(time.time())
            await self.write_async()

    async def advance_time(self, current_time):
        """ Trigger an update to the average, based on the current time.
        For most cases, this is time in blocks, but it can be any unit

        Args:
            current_time: time in some units

        """
        async with self.update_lock:
            time_units = 0
            for bounty in self.waiting:
                time_units += current_time - bounty.start_time

            self.liveliness.avg_wait = time_units / len(self.waiting) if len(self.waiting) > 0 else 0
            await self.write_async()

    async def write_async(self):
        """Get the json format of Liveliness, and write to the file"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.thread_pool_executor,
                                   self.write_sync,
                                   self.path,
                                   self.liveliness.json())

    def add_waiting_task(self, guid, start_time):
        """Add some bounty as waiting to be processed.

        Args:
            guid: bounty guid to add
            start_time: start time, in any units (either block number or time)
        """
        if guid not in self.waiting:
            self.waiting.append(WaitingTask(guid, start_time))

    def remove_waiting_task(self, guid):
        """Mark a task as done processing"""
        self.waiting.remove(WaitingTask(guid, None))

    def write_sync(self, path, content):
        """ Write the given content to the file at the given path.

        Args:
            path: file path to write to
            content: content to write into the file
        """
        with open(path, 'w') as f:
            try:
                with FileLock(f.fileno()):
                    f.write(content)
            except OSError:
                logger.exception('Unable to lock file')


class WaitingTask:
    """Some task waiting to be processed"""
    def __init__(self, guid, start_time):
        self.guid = guid
        self.start_time = start_time

    def __eq__(self, other):
        # Only care about guid for __eq__
        return isinstance(other, self.__class__) and other.guid == self.guid

    def __hash__(self):
        # Only care about guid for __hash__
        return hash(self.guid)
