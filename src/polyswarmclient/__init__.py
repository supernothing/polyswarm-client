import aiohttp
import asyncio
import base58
import json
import logging
import sys
import websockets 

from urllib.parse import urljoin
from polyswarmclient import bloom, events

from web3 import Web3
w3 = Web3()


def check_response(response):
    """Check the status of responses from polyswarmd

    Args:
        response: Response dict parsed from JSON from polyswarmd
    Returns:
        (bool): True if successful else False
    """
    status = response.get('status')
    ret = status and status == 'OK'
    if not ret:
        logging.error('Received unexpected failure response from polyswarmd: %s', response)
    return ret


def is_valid_ipfs_uri(ipfs_uri):
    # TODO: Further multihash validation
    try:
        return len(ipfs_uri) < 100 and base58.b58decode(ipfs_uri)
    except:
        pass

    logging.error('Invalid IPFS URI: %s', ipfs_uri)
    return False


class Client(object):
    def __init__(self, polyswarmd_addr, keyfile, password, api_key=None, tx_error_fatal=False, insecure_transport=False):
        if api_key and insecure_transport:
            raise ValueError('Refusing to send API key over insecure transport')

        protocol = 'http://' if insecure_transport else 'https://'
        self.polyswarmd_uri = protocol + polyswarmd_addr
        self.api_key = api_key

        self.tx_error_fatal = tx_error_fatal
        self.params = {}

        with open(keyfile, 'r') as f:
            self.priv_key = w3.eth.account.decrypt(f.read(), password)

        self.account = w3.eth.account.privateKeyToAccount(
            self.priv_key).address
        logging.info('Using account: %s', self.account)

        self.__session = None
        self.base_nonce = {
            'home': 0,
            'side': 0,
        }
        self.base_nonce_lock = {
            'home': asyncio.Lock(),
            'side': asyncio.Lock(),
        }
        self.__schedule = {
            'home': events.Schedule(),
            'side': events.Schedule(),
        }

        self.bounties = None
        self.staking = None
        self.offers = None

        # Events from client
        self.on_run = events.OnRunCallback()

        # Events from polyswarmd
        self.on_new_block = events.OnNewBlockCallback()
        self.on_new_bounty = events.OnNewBountyCallback()
        self.on_new_assertion = events.OnNewAssertionCallback()
        self.on_reveal_assertion = events.OnRevealAssertionCallback()
        self.on_new_verdict = events.OnNewVerdictCallback()
        self.on_quorum_reached = events.OnQuorumReachedCallback()
        self.on_settled_bounty = events.OnSettledBountyCallback()
        self.on_initialized_channel = events.OnInitializedChannelCallback()

        # Events scheduled on block deadlines
        self.on_reveal_assertion_due = events.OnRevealAssertionDueCallback()
        self.on_vote_on_bounty_due = events.OnVoteOnBountyDueCallback()
        self.on_settle_bounty_due = events.OnSettleBountyDueCallback()


    def run(self, loop=None):
        """Run this microengine
        Args:
            loop (asyncio.BaseEventLoop): Event loop to run on, defaults to default event loop
        """
        if not loop:
            loop = asyncio.get_event_loop()
        loop.run_until_complete(self.run_task(loop))


    async def run_task(self, loop):
        if self.api_key and not self.polyswarmd_uri.startswith('https://'):
            raise Exception('Refusing to send API key over insecure transport')

        self.params = {'account': self.account} if not self.api_key else {}
        headers = {'Authorization': self.api_key} if self.api_key else {}
        try:
            async with aiohttp.ClientSession(headers=headers) as self.__session:
                self.bounties = BountyClient(self)
                await self.bounties.get_parameters('home')
                await self.bounties.get_parameters('side')

                self.staking = StakingClient(self)
                await self.staking.get_parameters('home')
                await self.staking.get_parameters('side')

                self.offers = OffersClient(self)

                await self.on_run.run()
                await asyncio.gather(self.listen_for_events('home', loop), self.listen_for_events('side', loop))
        finally:
            self.__session = None
            self.bounties = None
            self.staking = None
            self.offers = None

    async def make_request(self, method, path, chain, json=None, track_nonce=False)
        """Make a request to polyswarmd, expecting a json response

        Args:
            method (str): HTTP method to use
            path (str): Path portion of URI to send request to
            chain (str): Which chain to operate on
            json (obj): JSON payload to send with request
            track_nonce (bool): Whether to track generated transaction and update nonce
        Returns:
            Response JSON parsed from polyswarmd
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parameter must be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = urljoin(self.polyswarmd_uri, path)

        params = self.params
        params['chain'] =  chain
        if track_nonce:
            await self.base_nonce_lock[chain].acquire()
            params['base_nonce'] = self.base_nonce[chain]

        try:
            async with self.__session.request(method, uri, params=params, json=json) as response:
                response = await response.json()
            logging.debug('%s %s?%s: %s', method, path, '&'.join([a + '=' + b for (a, b) in params.items()]), response)
        finally:
            result = response.get('result', {})
            transactions = result.get('transactions', [])
            if track_nonce and transactions:
                base_nonce[chain] += len(transactions)
                base_nonce_lock[chain].release()


        if not check_response(response):
            return None

        return response.get('result')


    async def post_transactions(self, transactions, chain='home'):
        """Post a set of (signed) transactions to Ethereum via polyswarmd, parsing the emitted events

        Args:
            transactions (List[Transaction]): The transactions to sign and post
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parameter must be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        signed = []
        for tx in transactions:
            s = w3.eth.account.signTransaction(tx, self.priv_key)
            raw = bytes(s['rawTransaction']).hex()
            signed.append(raw)

        response = await self.make_request('POST', '/transactions', chain, json={'transactions': signed})
        if response is None:
            response = {}

        if not response or 'errors' in response.get('result', {})):
            if self.tx_error_fatal:
                logging.error('Received fatal transaction error: %s', response)
                sys.exit(1)
            else:
                logging.error('Received transaction error: %s', response)

        return response


    async def update_base_nonce(self, chain='home')
        """Update account's nonce from polyswarmd
        Args:
            chain (str): Which chain to operate on
            Integer value of nonce
        """
        async with self.base_nonce_lock:
            base_nonce[chain] = await self.make_request('GET', '/nonce', chain)

    async def get_artifact(self, ipfs_uri, index):
        """Retrieve an artifact from IPFS via polyswarmd

        Args:
            ipfs_uri (str): IPFS hash of the artifact to retrieve
            index (int): Index of the sub artifact to retrieve
        Returns:
            (bytes): Content of the artifact
        """
        path = '/artifacts/{1}/{2}'.format(ipfs_uri, index)
        async with self.__session.get(uri, params=self.params) as response:
            if response.status == 200:
                return await response.read()

            return None


    # Async iterator helper class
    class __GetArtifacts(object):
        def __init__(self, client, ipfs_uri):
            self.i = 0
            self.client = client
            self.ipfs_uri = ipfs_uri

        async def __aiter__(self):
            return self

        async def __anext__(self):
            if not is_valid_ipfs_uri(self.ipfs_uri):
                raise StopAsyncIteration

            i = self.i
            self.i += 1

            if i < 256:
                content = await self.client.get_artifact(self.ipfs_uri, i)
                if content:
                    return content

            raise StopAsyncIteration


    def get_artifacts(self, ipfs_uri):
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        return Client.__GetArtifacts(self, ipfs_uri)


    async def list_artifacts(self, ipfs_uri):
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        if not is_valid_ipfs_uri(ipfs_uri):
            return []

        uri = '{0}/artifacts/{1}'.format(self.polyswarmd_uri, ipfs_uri)
        params = self.params
        async with self.__session.get(uri, params=self.params) as response:
            response = await response.json()
        logging.debug('GET /artifacts/%s: %s', ipfs_uri, response)
        if not check_response(response):
            return []

        return [(a['name'], a['hash']) for a in response.get('result', {})]


    def schedule(self, expiration, event, chain='home'):
        """Schedule an event to execute on a particular block

        Args:
            expiration (int): Which block to execute on
            event (Event): Event to trigger on expiration block
            chain (str): Which chain to operate on
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parameter must be "home" or "side"')
        self.__schedule[chain].put(expiration, event)


    async def __handle_scheduled_events(self, number, loop, chain='home'):
        """Perform scheduled events when a new block is reported

        Args:
            number (int): The current block number reported from polyswarmd
            loop (asyncio.BaseEventLoop): Event loop we're running on
            chain (str): Which chain to operate on
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parameter must be "home" or "side"')
        while self.__schedule[chain].peek() and self.__schedule[chain].peek()[0] < number:
            exp, task = self.__schedule[chain].get()
            if isinstance(task, events.RevealAssertion):
                loop.create_task(self.on_reveal_assertion_due.run(bounty_guid=task.guid, index=task.index, nonce=task.nonce,
                    verdicts=task.verdicts, metadata=task.metadata, chain=chain))
            elif isinstance(task, events.SettleBounty):
                loop.create_task(self.on_settle_bounty_due.run(bounty_guid=task.guid, chain=chain))
            elif isinstance(task, events.VoteOnBounty):
                loop.create_task(self.on_vote_on_bounty_due.run(bounty_guid=task.guid, verdicts=task.verdicts,
                    valid_bloom=task.valid_bloom, chain=chain))


    async def listen_for_events(self, loop, chain='home'):
        """Listen for events via websocket connection to polyswarmd

        Args:
            loop (asyncio.BaseEventLoop): Event loop we're running on
            chain (str): Which chain to operate on
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parameter must be "home" or "side"')
        assert(self.polyswarmd_uri.startswith('http'))

        # http:// -> ws://, https:// -> wss://
        wsuri = '{0}/events?chain={1}'.format(self.polyswarmd_uri, chain).replace('http', 'ws', 1)
        last_block = 0
        async with websockets.connect(wsuri) as ws:
            while True:
                event = json.loads(await ws.recv())
                if event['event'] == 'block':
                    number = event['data']['number']
                    if number <= last_block:
                        continue
                    if number % 100 == 0:
                        logging.debug('Block %s on chain %s', number, chain)
                    loop.create_task(self.on_new_block.run(number=number, chain=chain))
                    loop.create_task(self.__handle_scheduled_events(number, loop))
                elif event['event'] == 'bounty':
                    data = event['data']
                    logging.info('Received bounty on chain %s: %s', chain, data)
                    loop.create_task(self.on_new_bounty.run(**data, chain=chain))
                elif event['event'] == 'assertion':
                    data = event['data']
                    logging.info('Received assertion on chain %s: %s', chain, data)
                    loop.create_task(self.on_new_assertion.run(**data, chain=chain))
                elif event['event'] == 'reveal':
                    data = event['data']
                    logging.info('Received reveal on chain %s: %s', chain, data)
                    loop.create_task(self.on_reveal_assertion.run(**data, chain=chain))
                elif event['event'] == 'verdict':
                    data = event['data']
                    logging.info('Received verdict on chain %s: %s', chain, data)
                    loop.create_task(self.on_new_verdict.run(**data, chain=chain))
                elif event['event'] == 'quorum':
                    data = event['data']
                    logging.info('Received quorum on chain %s: %s', chain, data)
                    loop.create_task(self.on_quorum_reached.run(**data, chain=chain))
                elif event['event'] == 'settled_bounty':
                    data = event['data']
                    logging.info('Received settled bounty on chain %s: %s', chain, data)
                    loop.create_task(self.on_settled_bounty.run(**data, chain=chain))
                elif event['event'] == 'initialized_channel':
                    data = event['data']
                    logging.info('Received initialized_channel: %s', data)
                    loop.create_task(self.on_initialized_channel.run(**data, chain=chain))
