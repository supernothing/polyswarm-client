import asyncio
import logging
from abc import ABC, abstractmethod

from polyswarmclient import Client
from polyswarmclient.events import SettleBounty
from polyswarmclient.utils import asyncio_stop

logger = logging.getLogger(__name__)  # Initialize logger

MAX_TRIES = 10
BOUNTY_QUEUE_SIZE = 10
MAX_BOUNTIES_IN_FLIGHT = 10
MAX_BOUNTIES_PER_BLOCK = 1
BLOCK_DIVISOR = 1


class QueuedBounty(object):
    def __init__(self, amount, ipfs_uri, duration, api_key=None):
        self.amount = amount
        self.ipfs_uri = ipfs_uri
        self.duration = duration
        self.api_key = api_key

    def __repr__(self):
        return '({0}, {1}, {2})'.format(self.amount, self.ipfs_uri, self.duration)


class AbstractAmbassador(ABC):
    def __init__(self, client, testing=0, chains=None, watchdog=0, submission_rate=0):
        self.client = client
        self.chains = chains
        self.client.on_run.register(self.__handle_run)
        self.client.on_new_block.register(self.__handle_new_block)
        self.client.on_settle_bounty_due.register(self.__handle_settle_bounty)

        # Initialize in run_task to ensure we're on the right loop
        self.bounty_queue = None
        self.bounty_semaphore = None
        self.block_event = None

        self.watchdog = watchdog
        self.first_block = 0
        self.last_block = 0
        self.last_bounty_count = 0

        self.testing = testing
        self.bounties_posted = 0
        self.settles_posted = 0
        self.submission_rate = submission_rate

    @classmethod
    def connect(cls, polyswarmd_addr, keyfile, password, api_key=None, testing=0, insecure_transport=False, chains=None,
                watchdog=0, submission_rate=0):
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
        return cls(client, testing, chains, watchdog, submission_rate)

    @abstractmethod
    async def generate_bounties(self, chain):
        """Override this to submit bounties to the queue (using the push_bounty method)

        Args:
            chain (str): Chain we are operating on.
        """
        pass

    async def push_bounty(self, amount, ipfs_uri, duration, api_key=None):
        """Push a bounty onto the queue for submission

        Args:
            amount (int): Amount of NCT to place on the bounty
            ipfs_uri (str): URI for artifact(s) to be analyzed
            duration (int): Duration in blocks to accept assertions
            api_key (str): API key to use to submit, if None use default from client
        """
        bounty = QueuedBounty(amount, ipfs_uri, duration, api_key=api_key)
        logger.info('Queueing bounty %s', bounty)
        await self.bounty_queue.put(bounty)

    def run(self):
        """Run the Client on all of our chains."""
        self.client.run(self.chains)

    async def __handle_run(self, chain: str) -> None:
        """Asynchronously run a task on a given chain.

        Args:
            chain (str): Name of the chain to run.
        """
        asyncio.get_event_loop().create_task(self.run_task(chain))

    async def run_task(self, chain):
        """Iterate through the bounties an Ambassador wants to post on a given chain.

        Post each bounty to polyswarmd and schedule the bounty to be settled.

        Args:
            chain (str): Name of the chain to post bounties to.

        """
        self.bounty_queue = asyncio.Queue(maxsize=BOUNTY_QUEUE_SIZE)
        self.bounty_semaphore = asyncio.BoundedSemaphore(value=MAX_BOUNTIES_IN_FLIGHT)
        self.block_event = asyncio.Event()

        # Producer task
        asyncio.get_event_loop().create_task(self.generate_bounties(chain))

        # Consumer
        while True:
            # Wait for a block
            await self.block_event.wait()
            self.block_event.clear()

            bounties_this_block = 0
            while bounties_this_block < MAX_BOUNTIES_PER_BLOCK:
                # Exit if we are in testing mode
                if self.testing > 0 and self.bounties_posted >= self.testing:
                    logger.info('All testing bounties submitted')
                    return

                try:
                    bounty = self.bounty_queue.get_nowait()
                except asyncio.queues.QueueEmpty:
                    logger.debug('Queue empty, waiting for next block')
                    break

                if bounty is None:
                    logger.info('Got None for bounty value, moving on to next block')
                    break

                bounties_this_block += 1
                await self.bounty_semaphore.acquire()
                asyncio.get_event_loop().create_task(self.submit_bounty(bounty, chain))

    async def submit_bounty(self, bounty, chain):
        """Submit a bounty in a new task

        Args:
            bounty (QueuedBounty): Bounty to submit
            chain: Name of the chain to post to
        """
        assertion_reveal_window = await self.client.bounties.parameters[chain].get('assertion_reveal_window')
        arbiter_vote_window = await self.client.bounties.parameters[chain].get('arbiter_vote_window')
        bounty_fee = await self.client.bounties.parameters[chain].get('bounty_fee')

        tries = 0
        while tries < MAX_TRIES:
            balance = await self.client.balances.get_nct_balance(chain)

            # If we don't have the balance, don't submit. Wait and try a few times, then skip
            if balance < bounty.amount + bounty_fee:
                # Skip to next bounty, so one ultra high value bounty doesn't DOS ambassador
                if self.client.tx_error_fatal and tries >= MAX_TRIES:
                    logger.error('Failed %d attempts to post bounty due to low balance. Exiting', tries)
                    self.client.exit_code = 1
                    asyncio_stop()
                    return
                else:
                    tries += 1
                    logger.warning('Insufficient balance to post bounty on %s. Have %s NCT. Need %s NCT.', chain,
                                   balance, bounty.amount + bounty_fee, extra={'extra': bounty})
                    await asyncio.sleep(tries * tries)
                    continue

            await self.on_before_bounty_posted(bounty.amount, bounty.ipfs_uri, bounty.duration, chain)

            logger.info('Submitting bounty %s', self.bounties_posted, extra={'extra': bounty})
            bounties = await self.client.bounties.post_bounty(bounty.amount, bounty.ipfs_uri, bounty.duration, chain,
                                                              api_key=bounty.api_key)

            if not bounties:
                await self.on_bounty_post_failed(bounty.amount, bounty.ipfs_uri, bounty.duration, chain)
            else:
                self.bounties_posted += 1

            for b in bounties:
                guid = b['guid']
                expiration = int(b['expiration'])

                # Handle any additional steps in derived implementations
                await self.on_after_bounty_posted(guid, bounty.amount, bounty.ipfs_uri, expiration, chain)

                sb = SettleBounty(guid)
                self.client.schedule(expiration + assertion_reveal_window + arbiter_vote_window, sb, chain)

            self.bounty_queue.task_done()
            self.bounty_semaphore.release()
            return

        logger.warning('Failed %d attempts to post bounty due to low balance. Skipping', tries, extra={'extra': bounty})
        await self.on_bounty_post_failed(bounty.amount, bounty.ipfs_uri, bounty.duration, chain)

    async def __handle_new_block(self, number, chain):
        if number <= self.last_block:
            return

        self.last_block = number

        if self.block_event is not None and number % BLOCK_DIVISOR == 0:
            self.block_event.set()

        if not self.watchdog:
            return

        if not self.first_block:
            self.first_block = number
            return

        blocks = number - self.first_block
        if blocks % self.watchdog == 0 and self.bounties_posted == self.last_bounty_count:
            raise Exception('Bounties not processing, exiting with failure')

        self.last_bounty_count = self.bounties_posted

    async def __handle_settle_bounty(self, bounty_guid, chain):
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
        if self.testing > 0 and self.settles_posted >= self.testing:
            logger.info("All testing bounties complete, exiting")
            asyncio_stop()

        return ret

    async def on_before_bounty_posted(self, amount, ipfs_uri, duration, chain):
        """Override this to implement additional steps before the bounty is posted

        Args:
            amount (int): Amount to place this bounty for
            ipfs_uri (str): IPFS URI of the artifact to post
            duration (int): Duration of the bounty in blocks
            chain (str): Chain we are operating on
        """
        pass

    async def on_bounty_post_failed(self, amount, ipfs_uri, duration, chain):
        """Override this to implement additional steps when a bounty fails to post

        Args:
            amount (int): Amount to place this bounty for
            ipfs_uri (str): IPFS URI of the artifact to post
            duration (int): Duration of the bounty in blocks
            chain (str): Chain we are operating on
        """
        pass

    async def on_after_bounty_posted(self, guid, amount, ipfs_uri, expiration, chain):
        """Override this to implement additional steps after bounty is posted

        Args:
            guid (str): GUID of the posted bounty
            amount (int): Amount of the posted bounty
            ipfs_uri (str): URI of the artifact submitted
            expiration (int): Block number of bounty expiration
            chain (str): Chain we are operating on
        """
        pass
