import asyncio
import logging

from polyswarmclient import Client
from polyswarmclient.events import RevealAssertion, SettleBounty

logger = logging.getLogger(__name__)  # Initialize logger


class AbstractMicroengine(object):
    def __init__(self, client, testing=0, scanner=None, chains=None):
        self.client = client
        self.chains = chains
        self.scanner = scanner
        self.client.on_new_bounty.register(self.handle_new_bounty)
        self.client.on_reveal_assertion_due.register(self.handle_reveal_assertion)
        self.client.on_settle_bounty_due.register(self.handle_settle_bounty)

        self.testing = testing
        self.bounties_seen = 0
        self.reveals_posted = 0
        self.settles_posted = 0

    @classmethod
    def connect(cls, polyswarmd_addr, keyfile, password, api_key=None, testing=0, insecure_transport=False, scanner=None, chains=None):
        """Connect the Microengine to a Client.

        Args:
            polyswarmd_addr (str): URL of polyswarmd you are referring to.
            keyfile (str): Keyfile filename.
            password (str): Password associated with Keyfile.
            api_key (str): Your PolySwarm API key.
            testing (int): Number of testing bounties to use.
            insecure_transport (bool): Allow insecure transport such as HTTP?
            scanner (Scanner): `Scanner` instance to use.
            chains (set(str)):  Set of chains you are acting on.

        Returns:
            AbstractMicroengine: Microengine instantiated with a Client.
        """
        client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
        return cls(client, testing, scanner, chains)

    async def scan(self, guid, content, chain):
        """Override this to implement custom scanning logic

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            content (bytes): Content of the artifact to be scan
            chain (str): Chain we are operating on
        Returns:
            (bool, bool, str): Tuple of bit, verdict, metadata

        Note:
            | The meaning of the return types are as follows:
            |   - **bit** (*bool*): Whether to include this artifact in the assertion or not
            |   - **verdict** (*bool*): Whether this artifact is malicious or not
            |   - **metadata** (*str*): Optional metadata about this artifact
        """
        if self.scanner:
            return await self.scanner.scan(guid, content, chain)

        raise NotImplementedError("You must 1) override this scan method OR 2) provide a scanner to your Microengine constructor")

    def bid(self, guid, chain):
        """Override this to implement custom bid calculation logic

        Args:
            guid (str): GUID of the bounty under analysis, use to correlate with artifacts in the same bounty
            chain (str): Chain we are operating on
        Returns:
            (int): Amount of NCT to bid in base NCT units (10 ^ -18)
        """
        return self.client.bounties.parameters[chain]['assertion_bid_minimum']

    def run(self):
        """
        Run the `Client` on the Microengine's chains.
        """
        self.client.run(self.chains)

    async def handle_new_bounty(self, guid, author, amount, uri, expiration, chain):
        """Scan and assert on a posted bounty

        Args:
            guid (str): The bounty to assert on
            author (str): The bounty author
            amount (str): Amount of the bounty in base NCT units (10 ^ -18)
            uri (str): IPFS hash of the root artifact
            expiration (str): Block number of the bounty's expiration
            chain (str): Is this on the home or side chain?
        Returns:
            Response JSON parsed from polyswarmd containing placed assertions
        """
        self.bounties_seen += 1
        if self.testing > 0:
            if self.bounties_seen > self.testing:
                logger.warning('Received new bounty, but finished with testing mode')
                return []
            logger.info('Testing mode, %s bounties remaining', self.testing - self.bounties_seen)

        mask = []
        verdicts = []
        metadatas = []
        async for content in self.client.get_artifacts(uri):
            bit, verdict, metadata = await self.scan(guid, content, chain)
            mask.append(bit)
            verdicts.append(verdict)
            metadatas.append(metadata)

        if not any(mask):
            return []

        expiration = int(expiration)
        assertion_fee = self.client.bounties.parameters[chain]['assertion_fee']
        assertion_reveal_window = self.client.bounties.parameters[chain]['assertion_reveal_window']
        arbiter_vote_window = self.client.bounties.parameters[chain]['arbiter_vote_window']

        # Check that microengine has sufficient balance to handle the assertion
        bid = self.bid(guid, chain)
        balance = await self.client.balances.get_nct_balance(chain)
        if balance < assertion_fee + bid:
            logger.warning('Insufficient balance to post assertion for bounty on %s. Have %s need %s', chain, balance, assertion_fee + bid, extra={'extra': guid})
            if self.testing > 0:
                self.client.exit_code = 1
                self.client.stop()
            return []

        logger.info('Responding to bounty: %s', guid)
        nonce, assertions = await self.client.bounties.post_assertion(guid, bid, mask, verdicts, chain)
        for a in assertions:
            ra = RevealAssertion(guid, a['index'], nonce, verdicts, ';'.join(metadatas))
            self.client.schedule(expiration, ra, chain)

            sb = SettleBounty(guid)
            self.client.schedule(expiration + assertion_reveal_window + arbiter_vote_window, sb, chain)

        return assertions

    async def handle_reveal_assertion(self, bounty_guid, index, nonce, verdicts, metadata, chain):
        """
        Callback registered in `__init__` to handle the reveal assertion.

        Args:
            guid (str): GUID of the bounty being asserted on
            index (int): Index of the assertion to reveal
            nonce (str): Secret nonce used to reveal assertion
            verdicts (List[bool]): List of verdicts for each artifact in the bounty
            metadata (str): Optional metadata
            chain (str): Chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        self.reveals_posted += 1
        if self.testing > 0:
            if self.reveals_posted > self.testing:
                logger.warning('Scheduled reveal, but finished with testing mode')
                return []
            logger.info('Testing mode, %s reveals remaining', self.testing - self.reveals_posted)
        return await self.client.bounties.post_reveal(bounty_guid, index, nonce, verdicts, metadata, chain)

    async def handle_settle_bounty(self, bounty_guid, chain):
        """
        Callback registered in `__init__` to handle a settled bounty.

        Args:
            guid (str): GUID of the bounty being asserted on
            chain (str): Chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        self.settles_posted += 1
        if self.testing > 0:
            if self.settles_posted > self.testing:
                logger.warning('Scheduled settle, but finished with testing mode')
                return []
            logger.info('Testing mode, %s settles remaining', self.testing - self.settles_posted)

        ret = await self.client.bounties.settle_bounty(bounty_guid, chain)
        if self.testing > 0 and self.settles_posted >= self.testing:
            logger.info("All testing bounties complete, exiting")
            self.client.stop()
        return ret
