from functools import total_ordering
from queue import PriorityQueue


class Callback(object):
    def __init__(self):
        self.cbs = []

    def register(self, f):
        self.cbs.append(f)

    def remove(self, f):
        self.cbs.remove(f)

    async def run(self, *args, **kwargs):
        ret = []
        for cb in self.cbs:
            local_ret = await cb(*args, **kwargs)
            if local_ret is not None:
                ret.append(local_ret)
        return ret


class Schedule(object):
    def __init__(self):
        self.queue = PriorityQueue()

    def empty(self):
        return self.queue.empty()

    def peek(self):
        return self.queue.queue[0] if self.queue.queue else None

    def get(self):
        return self.queue.get()

    def put(self, block, event):
        self.queue.put((block, event))


@total_ordering
class Event(object):
    def __init__(self, guid):
        self.guid = guid

    def __eq__(self, other):
        return self.guid == other.guid

    def __lt__(self, other):
        return self.guid < other.guid


class RevealAssertion(Event):
    """An assertion scheduled to be publically revealed"""

    def __init__(self, guid, index, nonce, verdicts, metadata):
        """Initialize a reveal secret assertion event

        Args:
            guid (str): GUID of the bounty being asserted on
            index (int): Index of the assertion to reveal
            nonce (str): Secret nonce used to reveal assertion
            verdicts (List[bool]): List of verdicts for each artifact in the bounty
            metadata (str): Optional metadata
        """
        super().__init__(guid)
        self.index = index
        self.nonce = nonce
        self.verdicts = verdicts
        self.metadata = metadata


class VoteOnVerdict(Event):
    """A scheduled vote from an arbiter"""

    def __init__(self, guid, verdicts, valid_bloom):
        """Initialize a vote on verdict event

        Args:
            guid (str): GUID of the bounty being voted on
            verdicts (List[bool]): List of verdicts for each artifact in the bounty
            valid_bloom (bool): Is the bloom filter submitted with the bounty valid
        """
        super().__init__(guid)
        self.verdicts = verdicts
        self.valid_bloom = valid_bloom


class SettleBounty(Event):
    """A bounty scheduled to be settled"""

    def __init__(self, guid):
        """Initialize an settle bounty event

        Args:
            guid (str): GUID of the bounty being asserted on
        """
        super().__init__(guid)
