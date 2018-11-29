import asyncio
import logging
import sys

from abc import ABC, abstractmethod
from polyswarmclient import Client
from polyswarmclient.events import SettleBounty

logger = logging.getLogger(__name__)  # Initialize logger
MAX_TRIES = 10


class AbstractAmbassador(ABC):
    def __init__(self, client, testing=0, chains=None, watchdog=0):
        self.client = client
        self.chains = chains
        self.client.on_run.register(self.handle_run)
        self.client.on_settle_bounty_due.register(self.handle_settle_bounty)

        self.watchdog = watchdog
        self.first_block = 0
        self.last_bounty_count = 0
        if self.watchdog:
            self.client.on_new_block.register(self.handle_new_block)

        self.testing = testing
        self.bounties_posted = 0
        self.settles_posted = 0

    @classmethod
    def connect(cls, polyswarmd_addr, keyfile, password, api_key=None, testing=0, insecure_transport=False, chains=None, watchdog=0):
        """Connect the Ambassador to a Client.

        Args:
            polyswarmd_addr (str): URL of polyswarmd you are referring to.
            keyfile (str): Keyfile filename.
            password (str): Password associated with Keyfile.
            api_key (str): Your PolySwarm API key.
            testing (int): Number of testing bounties to use.
            insecure_transport (bool): Allow insecure transport such as HTTP?
            chains (set(str)):  Set of chains you are acting on.

        Returns:
            AbstractAmbassador: Ambassador instantiated with a Client.
        """
        client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
        return cls(client, testing, chains, watchdog)

    @abstractmethod
    async def next_bounty(self, chain):
        """Override this to implement different bounty submission queues

        Args:
            chain (str): Chain we are operating on.
        Returns:
            (int, str, int): Tuple of amount, ipfs_uri, duration, None to terminate submission

        Note:
            | The meaning of the return types are as follows:
            |   - **amount** (*int*): Amount to place this bounty for
            |   - **ipfs_uri** (*str*): IPFS URI of the artifact to post
            |   - **duration** (*int*): Duration of the bounty in blocks
        """
        pass

    def on_bounty_posted(self, guid, amount, ipfs_uri, expiration, chain):
        """Override this to implement additional steps after bounty submission

        Args:
            guid (str): GUID of the posted bounty
            amount (int): Amount of the posted bounty
            ipfs_uri (str): URI of the artifact submitted
            expiration (int): Block number of bounty expiration
            chain (str): Chain we are operating on
        """
        pass

    def run(self):
        """Run the Client on all of our chains."""
        self.client.run(self.chains)

    async def handle_run(self, chain: str) -> None:
        """
        Asynchronously run a task on a given chain.

        Args:
            chain (str): Name of the chain to run.
        """
        asyncio.get_event_loop().create_task(self.run_task(chain))

    async def run_task(self, chain):
        """
            Iterate through the bounties an Ambassador wants to post on a given chain.
            Post each bounty to polyswarmd and schedule the bounty to be settled.

        Args:
            chain (str): Name of the chain to post bounties to.

        """
        assertion_reveal_window = self.client.bounties.parameters[chain]['assertion_reveal_window']
        arbiter_vote_window = self.client.bounties.parameters[chain]['arbiter_vote_window']
        bounty_fee = self.client.bounties.parameters[chain]['bounty_fee']

        # HACK: In testing mode we start up ambassador/arbiter/microengine
        # immediately and start submitting bounties, however arbiter has to wait
        # a block for its staking tx to be mined before it starts respoonding.
        # Add in a sleep for now, this will be addressed properly in
        # polyswarm-client#5
        if self.testing > 0:
            logger.info('Waiting for arbiter and microengine')
            await asyncio.sleep(5)

        bounty = await self.next_bounty(chain)
        tries = 0
        while bounty is not None:
            # Exit if we are in testing mode
            if self.testing > 0 and self.bounties_posted >= self.testing:
                logger.info('All testing bounties submitted')
                break

            amount, ipfs_uri, duration = bounty
            balance = await self.client.balances.get_nct_balance(chain)
            # If we don't have the balance, don't submit. Wait and try a few times, then skip
            if balance < amount + bounty_fee and tries >= MAX_TRIES:
                    # Skip to next bounty, so one ultra high value bounty doesn't DOS ambassador
                    if self.testing:
                        logger.error('Failed %d attempts to post bounty to low balance. Exiting', tries)
                        self.client.exit_code = 1
                        self.client.stop()
                        return
                    else:
                        logger.warning('Failed %d attempts to post bounty due to low balance. Skipping', tries, extra={'extra': bounty})
                        tries = 0
                        bounty = await self.next_bounty(chain)
                        continue
            elif balance < amount + bounty_fee:
                tries += 1
                logger.warning('Insufficient balance to post bounty on %s. Have %s, need %s.', chain, balance, amount+bounty_fee, extra={'extra': bounty})
                await asyncio.sleep(tries * tries)
                continue

            self.bounties_posted += 1
            logger.info('Submitting bounty %s', self.bounties_posted, extra={'extra': bounty})
            bounties = await self.client.bounties.post_bounty(amount, ipfs_uri, duration, chain)

            for b in bounties:
                guid = b['guid']
                expiration = int(b['expiration'])

                # Handle any additional steps in derived implementations
                self.on_bounty_posted(guid, amount, ipfs_uri, expiration, chain)

                sb = SettleBounty(guid)
                self.client.schedule(expiration + assertion_reveal_window + arbiter_vote_window, sb, chain)

            tries = 0
            bounty = await self.next_bounty(chain)

    async def handle_new_block(self, number, chain):
        if not self.watchdog:
            return

        if not self.first_block:
            self.first_block = number
            return

        blocks = number - self.first_block
        if blocks % self.watchdog == 0 and self.bounties_posted == self.last_bounty_count:
            raise Exception('Bounties not processing, exiting with failure')

        self.last_bounty_count = self.bounties_posted

    async def handle_settle_bounty(self, bounty_guid, chain):
        """
        When a bounty is scheduled to be settled, actually settle the bounty to the given chain.

        Args:
            bounty_guid (str): GUID of the bounty to be submitted.
            chain (str): Name of the chain where the bounty is to be posted.
        Returns:
            Response JSON parsed from polyswarmd containing emitted events.
        """
        self.settles_posted += 1
        if self.testing > 0:
            if self.settles_posted > self.testing:
                logger.warning('Scheduled settle, but finished with testing mode')
                return []
            logger.info('Testing mode, %s settles remaining', self.testing - self.settles_posted)

        ret = await self.client.bounties.settle_bounty(bounty_guid, chain)
        if self.testing > 0 and self.settles_posted == self.testing:
            logger.info("All testing bounties complete, exiting")
            self.client.stop()
        return ret
