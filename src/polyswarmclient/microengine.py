import functools
from polyswarmclient import Client
from polyswarmclient.events import RevealAssertion, SettleBounty

class Microengine(object):
    def __init__(self, polyswarmd_uri, keyfile, password, api_key=None, testing=-1, insecure_transport=False, scanner=None):
        self.testing = testing
        self.scanner = scanner
        self.client = Client(polyswarmd_uri, keyfile, password, api_key, testing > 0, insecure_transport)
        self.client.on_new_bounty.register(functools.partial(Microengine.handle_new_bounty, self))
        self.client.on_reveal_assertion_due.register(functools.partial(Microengine.handle_reveal_assertion, self))
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
        if self.scanner:
            return await self.scacnner.scan(guid, content)

        return True, True, ''

    def bid(self, guid):
        """Override this to implement custom bid calculation logic

        Args:
            guid (str): GUID of the bounty under analysis, use to correlate with artifacts in the same bounty
        Returns:
            (int): Amount of NCT to bid in base NCT units (10 ^ -18)
        """
        return self.client.bounty_parameters['home']['assertion_bid_minimum']


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

        expiration = int(expiration)
        assertion_reveal_window = self.client.bounty_parameters['home']['assertion_reveal_window']
        arbiter_vote_window = self.client.bounty_parameters['home']['arbiter_vote_window']
        nonce, assertions = await self.client.post_assertion(guid, self.bid(guid), mask, verdicts, chain)
        for a in assertions:
            ra = RevealAssertion(guid, a['index'], nonce, verdicts, ';'.join(metadatas))
            self.client.schedule(expiration, ra, chain)

            sb = SettleBounty(guid)
            self.client.schedule(expiration + assertion_reveal_window + arbiter_vote_window, sb, chain)

        return assertions

    async def handle_reveal_assertion(self, bounty_guid, index, nonce, verdicts, metadata, chain):
        return await self.client.post_reveal(bounty_guid, index, nonce, verdicts, metadata, chain)


    async def handle_settle_bounty(self, bounty_guid, chain):
        return await self.client.settle_bounty(bounty_guid, chain)
