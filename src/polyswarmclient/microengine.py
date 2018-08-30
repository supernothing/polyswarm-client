import functools
from polyswarmclient import Client

class Microengine(object):
    def __init__(self, polyswarmd_uri, keyfile, password, api_key=None, testing=False):
        self.testing = testing
        self.client = Client(polyswarmd_uri, keyfile, password, api_key, testing)
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
        return True, True, ''

    def bid(self, guid):
        """Override this to implement custom bid calculation logic

        Args:
            guid (str): GUID of the bounty under analysis, use to correlate with artifacts in the same bounty
        Returns:
            (int): Amount of NCT to bid in base NCT units (10 ^ -18)
        """
        return MINIMUM_BID


    async def handle_new_bounty(self, session, guid, author, uri, amount,
                                  expiration):
        """Scan and assert on a posted bounty

        Args:
            guid (str): The bounty to assert on
            author (str): The bounty author
            uri (str): IPFS hash of the root artifact
            amount (str): Amount of the bounty in base NCT units (10 ^ -18)
            expiration (int): Block number of the bounty's expiration
        Returns:
            Response JSON parsed from polyswarmd containing placed assertions
        """
        mask = []
        verdicts = []
        metadatas = []
        for content in self.client.get_artifacts(uri):
            bit, verdict, metadata = await self.scan(guid, content)
            mask.append(bit)
            verdicts.append(verdict)
            metadatas.append(metadata)

        nonce, assertions = await self.client.post_assertion(guid, self.bid(guid), mask, verdicts)
        for a in assertions:
            ra = RevealAssertion(guid, a['index'], nonce, verdicts, ';'.join(metadatas))
            self.schedule.put(expiration, ra)

            sb = self.SettleBounty(guid)
            self.schedule_put(expiration + ASSERTION_REVEAL_WINDOW + ARBITER_VOTE_WINDOW, sb)

        return assertions

    async def handle_reveal_assertion(self, guid, index, nonce, verdicts, metadata):
        return await self.client.post_reveal(guid, index, nonce, verdicts, metadata)


    async def handle_settle_bounty(self, guid):
        return await self.client.settle_bounty(guid)
