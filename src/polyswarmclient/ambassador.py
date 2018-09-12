import asyncio
import functools
from polyswarmclient import Client
from polyswarmclient.events import SettleBounty


class Ambassador(object):
    def __init__(self, polyswarmd_uri, keyfile, password, chain='home', api_key=None, testing=-1, insecure_transport=False):
        self.chain = chain
        self.testing = testing
        self.client = Client(polyswarmd_uri, keyfile, password, api_key, testing > 0, insecure_transport)
        self.client.on_run.register(functools.partial(Ambassador.handle_run, self))
        self.client.on_settle_bounty_due.register(functools.partial(Microengine.handle_settle_bounty, self))


    async def next_artifact(self):
        """Override this to implement different artifact submission queues

        Returns:
            (int, str, int): Tuple of amount, ipfs_uri, duration, None to terminate submission

            amount (int): Amount to place this bounty for
            ipfs_uri (str): IPFS URI of the artifact to post
            duration (int): Duration of the bounty in blocks
        """
        return None


    def run(self, loop=None):
        self.client.run(loop)


    async def handle_run(self, loop, chain):
        loop.create_task(self.run_task(chain))


    async def run_task(self, chain):
        assertion_reveal_window = self.client.bounty_parameters[chain]['assertion_reveal_window']
        arbiter_vote_window = self.client.bounty_parameters[chain]['arbiter_vote_window']

        artifact = await self.next_artifact()
        while artifact is not None:
            amount, ipfs_uri, duration = artifact
            bounties = self.client.post_bounty(amount, uri, duration, self.chain)

            for bounty in bounties:
                expiration = bounty['expiration']
                sb = SettleBounty(guid)
                self.client.schedule(expiration + assertion_reveal_window + arbiter_vote_window, sb, chain)

            artifact = await self.next_artifact()


    async def handle_settle_bounty(self, bounty_guid, chain):
        return await self.client.settle_bounty(bounty_guid, chain)
