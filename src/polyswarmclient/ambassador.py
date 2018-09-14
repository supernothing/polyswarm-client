import asyncio
import functools
import logging
import sys

from polyswarmclient import Client
from polyswarmclient.events import SettleBounty


class Ambassador(object):
    def __init__(self, polyswarmd_uri, keyfile, password, api_key=None, testing=0, insecure_transport=False, chains={'home'}):
        self.chains = chains
        self.client = Client(polyswarmd_uri, keyfile, password, api_key, testing > 0, insecure_transport)
        self.client.on_run.register(functools.partial(Ambassador.handle_run, self))
        self.client.on_settle_bounty_due.register(functools.partial(Ambassador.handle_settle_bounty, self))

        self.testing = testing
        self.bounties_posted = 0
        self.settles_posted = 0

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

    def run(self):
        self.client.run(self.chains)

    async def handle_run(self, chain):
        asyncio.get_event_loop().create_task(self.run_task(chain))

    async def run_task(self, chain):
        assertion_reveal_window = self.client.bounties.parameters[chain]['assertion_reveal_window']
        arbiter_vote_window = self.client.bounties.parameters[chain]['arbiter_vote_window']

        bounty = await self.next_bounty(chain)
        while bounty is not None:
            # Exit if we are in testing mode
            if self.testing > 0 and self.bounties_posted >= self.testing:
                logging.info('All testing bounties submitted')
                break
            self.bounties_posted += 1

            logging.info('Submitting bounty %s: %s', self.bounties_posted, bounty)
            amount, ipfs_uri, duration = bounty
            bounties = await self.client.bounties.post_bounty(amount, ipfs_uri, duration, chain)

            for b in bounties:
                guid = b['guid']
                expiration = int(b['expiration'])

                sb = SettleBounty(guid)
                self.client.schedule(expiration + assertion_reveal_window + arbiter_vote_window, sb, chain)

            bounty = await self.next_bounty(chain)

    async def handle_settle_bounty(self, bounty_guid, chain):
        self.settles_posted += 1
        if self.testing > 0 and self.settles_posted > self.testing:
            logging.warning('Scheduled settle, but finished with testing mode')
            return []
        logging.info('Testing mode, %s settles remaining', self.testing - self.settles_posted)

        ret = await self.client.bounties.settle_bounty(bounty_guid, chain)
        if self.testing > 0 and self.settles_posted == self.testing:
            logging.info("All testing bounties complete, exiting")
            self.client.stop()
        return ret
