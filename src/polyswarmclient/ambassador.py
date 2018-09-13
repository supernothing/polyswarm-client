import asyncio
import functools
import logging
import sys

from polyswarmclient import Client
from polyswarmclient.events import SettleBounty


class Ambassador(object):
    def __init__(self, polyswarmd_uri, keyfile, password, api_key=None, testing=-1, insecure_transport=False, chains={'home'}):
        self.chains = chains
        self.testing = testing
        self.client = Client(polyswarmd_uri, keyfile, password, api_key, testing > 0, insecure_transport)
        self.client.on_run.register(functools.partial(Ambassador.handle_run, self))
        self.client.on_settle_bounty_due.register(functools.partial(Ambassador.handle_settle_bounty, self))

    async def next_bounty(self, chain):
        """Override this to implement different bounty submission queues

        Args:
            chain (str): Chain we are operating on
        Returns:
            (int, str, int): Tuple of amount, ipfs_uri, duration, None to terminate submission

            amount (int): Amount to place this bounty for
            ipfs_uri (str): IPFS URI of the artifact to post
            duration (int): Duration of the bounty in blocks
        """
        return None

    def run(self, loop=None):
        self.client.run(loop, self.chains)

    async def handle_run(self, loop, chain):
        loop.create_task(self.run_task(chain))

    async def run_task(self, chain):
        assertion_reveal_window = self.client.bounties.parameters[chain]['assertion_reveal_window']
        arbiter_vote_window = self.client.bounties.parameters[chain]['arbiter_vote_window']

        bounty = await self.next_bounty(chain)
        while bounty is not None:
            # Exit if we are in testing mode
            if self.testing == 0:
                logging.info('All testing bounties submitted, exiting...')
                sys.exit(0)
            self.testing -= 1

            logging.info('Submitting bounty: %s', bounty)
            amount, ipfs_uri, duration = bounty
            bounties = await self.client.bounties.post_bounty(amount, ipfs_uri, duration, chain)

            for b in bounties:
                guid = b['guid']
                expiration = int(b['expiration'])

                sb = SettleBounty(guid)
                self.client.schedule(expiration + assertion_reveal_window + arbiter_vote_window, sb, chain)

            bounty = await self.next_bounty(chain)

    async def handle_settle_bounty(self, bounty_guid, chain):
        return await self.client.bounties.settle_bounty(bounty_guid, chain)
