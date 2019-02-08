import asyncio
import os
import sys

from ethereum.utils import sha3

TASK_TIMEOUT = 1.0
MAX_WAIT = 600


def int_to_bytes(i):
    h = hex(i)[2:]
    return bytes.fromhex('0' * (64 - len(h)) + h)


def int_from_bytes(b):
    return int.from_bytes(b, byteorder='big')


def bool_list_to_int(bs):
    return sum([1 << n if b else 0 for n, b in enumerate(bs)])


def int_to_bool_list(i):
    s = format(i, 'b')
    return [x == '1' for x in s[::-1]]


def calculate_commitment(account, verdicts, nonce=None):
    if nonce is None:
        nonce = os.urandom(32)

    if isinstance(nonce, int):
        nonce = int_to_bytes(nonce)

    account = int(account, 16)
    commitment = sha3(int_to_bytes(verdicts ^ int_from_bytes(sha3(nonce)) ^ account))
    return int_from_bytes(nonce), int_from_bytes(commitment)


def asyncio_join():
    """Gather all remaining tasks, assumes loop is not running"""
    loop = asyncio.get_event_loop()
    pending = asyncio.Task.all_tasks(loop)

    loop.run_until_complete(asyncio.wait(pending, loop=loop, timeout=TASK_TIMEOUT))


def asyncio_stop():
    """Stop the main event loop"""
    loop = asyncio.get_event_loop()
    pending = asyncio.Task.all_tasks(loop)

    for task in pending:
        task.cancel()


def exit(exit_status):
    """Exit the program entirely."""
    if sys.platform == 'win32':
        # XXX: v. hacky. We need to find out what is hanging sys.exit()
        os._exit(exit_status)
    else:
        sys.exit(exit_status)
