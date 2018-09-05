import functools
from polyswarmclient import Client
from polyswarmclient.events import VoteOnBounty, SettleBounty
from polyswarmclient.bloom import BloomFilter, FILTER_BITS


def calculate_bloom(artifacts):
    bf = BloomFilter()
    for _, h in artifacts:
        bf.add(h.encode('utf-8'))

    v = int(bf)
    ret = []
    d = (1 << 256) - 1
    for _ in range(FILTER_BITS // 256):
        ret.insert(0, v % d)
        v //= d

    return ret


class Arbiter(object):
    def __init__(self, polyswarmd_uri, keyfile, password, api_key=None, testing=-1):
        self.testing = testing
        self.client = Client(polyswarmd_uri, keyfile, password, api_key, testing > 0)
        self.client.on_new_bounty.register(functools.partial(Microengine.handle_new_bounty, self))
        self.client.on_vote_on_bounty_due.register(functools.partial(Microengine.handle_vote_on_bounty, self))
        self.client.on_settle_bounty_due.register(functools.partial(Microengine.handle_settle_bounty, self))

    async def scan(self, guid, content):
        """Override this to implement custom scanning logic

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            content (bytes): Content of the artifact to be scan
        Returns:
            (bool, bool, str): Tuple of bit, verdict, metadata

            bit (bool): Whether to include this artifact in the assertion or not
            verdict (bool): Whether this artifact is malicious or not
            metadata (str): Optional metadata about this artifact
        """
        return True, True, ''


    def run(self, event_loop=None):
        self.client.run(event_loop)


    async def handle_new_bounty(self, guid, author, uri, amount, expiration, chain):
        """Scan and assert on a posted bounty

        Args:
            guid (str): The bounty to assert on
            author (str): The bounty author
            uri (str): IPFS hash of the root artifact
            amount (str): Amount of the bounty in base NCT units (10 ^ -18)
            expiration (str): Block number of the bounty's expiration
            chain (str): Is this on the home or side chain?
        Returns:
            Response JSON parsed from polyswarmd containing placed assertions
        """
        mask = []
        verdicts = []
        metadatas = []
        async for content in self.client.get_artifacts(uri):
            bit, verdict, metadata = await self.scan(guid, content)
            mask.append(bit)
            verdicts.append(verdict)
            metadatas.append(metadata)

        bounty = await self.client.get_bounty(guid)
        artifacts = await self.client.list_artifacts(uri)
        bloom = self.calculate_bloom(artifacts)
        valid_bloom = int(bounty.get('bloom', 0)) == bloom.value

        expiration = int(expiration)
        assertion_reveal_window = self.client.bounty_parameters['home']['assertion_reveal_window']
        arbiter_vote_window = self.client.bounty_parameters['home']['arbiter_vote_window']

        vb = VoteOnBounty(guid, verdicts, valid_bloom)
        self.client.schedule(expiration + assertion_reveal_window, vb, chain)

        sb = SettleBounty(guid)
        self.client.schedule(expiration + assertion_reveal_window + arbiter_vote_window, sb, chain)


    async def handle_vote_on_bounty(self, bounty_guid, verdicts, valid_bloom, chain):
        return await self.client.post_vote(bounty_guid, verdicts, valid_bloom, chain)


    async def handle_settle_bounty(self, bounty_guid, chain):
        return await self.client.settle_bounty(bounty_guid, chain)
