import aiohttp
import asyncio
import base58
import json
import logging
import sys
import websockets 
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
    return status and status == 'OK'


def is_valid_ipfs_uri(ipfs_uri):
    # TODO: Further multihash validation
    try:
        return len(ipfs_uri) < 100 and base58.b58decode(ipfs_uri)
    except:
        pass

    return False


class Client(object):
    def __init__(self, polyswarmd_uri, keyfile, password, api_key=None, tx_error_fatal=False):
        self.polyswarmd_uri = polyswarmd_uri
        self.api_key = api_key
        self.tx_error_fatal = tx_error_fatal
        self.params = {}

        with open(keyfile, 'r') as f:
            self.priv_key = w3.eth.account.decrypt(f.read(), password)

        self.account = w3.eth.account.privateKeyToAccount(
            self.priv_key).address
        logging.info('Using account: %s', self.account)

        self.__session = None
        self.__schedule = {
            'home': events.Schedule(),
            'side': events.Schedule()
        }

        self.bounty_parameters = {}

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
        self.on_vote_on_verdict_due = events.OnVoteOnVerdictDueCallback()
        self.on_settle_bounty_due = events.OnSettledBountyCallback()


    def run(self, event_loop = None):
        """Run this microengine
        """
        if event_loop is None:
            event_loop = asyncio.get_event_loop()

        event_loop.run_until_complete(self.__run())


    async def __run(self):
        self.params = {'account': self.account} if not self.api_key else {}
        headers = {'Authorization': self.api_key} if self.api_key else {}
        async with aiohttp.ClientSession(headers=headers) as self.__session:
            self.bounty_parameters['home'] = await self.get_bounty_parameters('home')
            self.bounty_parameters['side'] = await self.get_bounty_parameters('side')

            await self.on_run.run()
            await asyncio.gather(self.listen_for_events('home'), self.listen_for_events('side'))


    def schedule(self, expiration, event, chain='home'):
        assert(chain == 'home' or chain == 'side')
        self.__schedule[chain].put(expiration, event)


    async def __handle_scheduled_events(self, number, chain='home'):
        """Perform scheduled events when a new block is reported

        Args:
            number (int): The current block number reported from polyswarmd
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        assert(chain == 'home' or chain == 'side')
        ret = []
        while self.__schedule[chain].peek() and self.__schedule[chain].peek()[0] < number:
            exp, task = self.__schedule[chain].get()
            if isinstance(task, events.RevealAssertion):
                ret.append(await self.on_reveal_assertion_due.run(bounty_guid=task.guid, index=task.index, nonce=task.nonce,
                    verdicts=task.verdicts, metadata=task.metadata, chain=chain))
            elif isinstance(task, events.SettleBounty):
                ret.append(await self.on_settle_bounty_due.run(bounty_guid=task.guid, chain=chain))
            elif isinstance(task, events.VoteOnVerdict):
                ret.append(await self.on_vote_on_verdict.run(bounty_guid=task.guid, verdicts=task.verdicts,
                    valid_bloom=task.valid_bloom, chain=chain))

        return ret


    async def get_bounty_parameters(self, chain='home'):
        """Get bounty parameters from polyswarmd

        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        assert(chain == 'home' or chain == 'side')
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        uri = '{0}/bounties/parameters'.format(self.polyswarmd_uri)

        params = self.params
        params['chain'] = chain
        async with self.__session.get(uri, params=params) as response:
            response = await response.json()
        logging.debug('GET /bounties/parameters?chain=%s: %s', chain, response)
        if not check_response(response):
            return None

        try:
            return response['result']
        except:
            logging.warning('expected bounty parameters, got: %s', response)
            return None


    async def get_artifact(self, ipfs_uri, index):
        """Retrieve an artifact from IPFS via polyswarmd

        Args:
            ipfs_uri (str): IPFS hash of the artifact to retrieve
            index (int): Index of the sub artifact to retrieve
        Returns:
            (bytes): Content of the artifact
        """
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        if not is_valid_ipfs_uri(ipfs_uri):
            return None

        uri = '{0}/artifacts/{1}/{2}'.format(
            self.polyswarmd_uri, ipfs_uri, index)
        params = self.params
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
            i = self.i
            self.i += 1

            if i < 256:
                content = await self.client.get_artifact(self.ipfs_uri, i)
                if content:
                    return content

            raise StopAsyncIteration


    def get_artifacts(self, ipfs_uri):
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        return Client.__GetArtifacts(self, ipfs_uri)


    async def post_transactions(self, transactions, chain='home'):
        """Post a set of (signed) transactions to Ethereum via polyswarmd, parsing the emitted events

        Args:
            transactions (List[Transaction]): The transactions to sign and post
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        assert(chain == 'home' or chain == 'side')
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        signed = []
        for tx in transactions:
            s = w3.eth.account.signTransaction(tx, self.priv_key)
            raw = bytes(s['rawTransaction']).hex()
            signed.append(raw)

        uri = '{0}/transactions'.format(self.polyswarmd_uri)

        params = self.params
        params['chain'] = chain
        async with self.__session.post(uri, params=self.params, json={'transactions': signed}) as response:
            j = await response.json()
        logging.debug('POST /transactions?chain=%s: %s', chain, j)
        if self.tx_error_fatal and 'errors' in j.get('result', {}):
            logging.error('Received fatal transaction error: %s', j)
            sys.exit(1)

        return j


    async def post_bounty(self, amount, uri, duration, chain='home'):
        """Post a bounty to polyswarmd

        Args:
            amount (int): The amount to put up as a bounty
            uri (str): URI of artifacts
            duration (int): Number of blocks to accept new assertions
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        assert(chain == 'home' or chain == 'side')
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        uri = '{0}/bounties'.format(self.polyswarmd_uri)
        bounty = {
            'amount': str(amount),
            'uri': uri,
            'duration': duration,
        }

        params = self.params
        params['chain'] = chain
        async with self.__session.post(uri, params=self.params, json=bounty) as response:
            response = await response.json()
        logging.debug('POST /bounties?chain=%s: %s', chain, j)
        if not check_response(response):
            return []

        response = await self.post_transactions(response['result']['transactions'], chain)
        if not check_response(response):
            return []

        try:
            return response['result']['bounties']
        except:
            logging.warning('expected bounty, got: %s', response)
            return []


    async def post_assertion(self, guid, bid, mask, verdicts, chain='home'):
        """Post an assertion to polyswarmd

        Args:
            guid (str): The bounty to assert on
            bid (int): The amount to bid
            mask (List[bool]): Which artifacts in the bounty to assert on
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        assert(chain == 'home' or chain == 'side')
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        uri = '{0}/bounties/{1}/assertions'.format(
            self.polyswarmd_uri, guid)
        assertion = {
            'bid': str(bid),
            'mask': mask,
            'verdicts': verdicts,
        }

        params = self.params
        params['chain'] = chain
        async with self.__session.post(uri, params=self.params, json=assertion) as response:
            response = await response.json()
        logging.debug('POST /bounties/%s/assertions?chain=%s: %s', chain, guid, response)
        if not check_response(response):
            return None, []

        nonce = response['result']['nonce']
        response = await self.post_transactions(response['result']['transactions'], chain)
        if not check_response(response):
            return None, []

        try:
            return nonce, response['result']['assertions']
        except:
            logging.warning('expected assertion, got: %s', response)
            return None, []


    async def post_reveal(self, guid, index, nonce, verdicts, metadata, chain='home'):
        """Post an assertion reveal to polyswarmd

        Args:
            guid (str): The bounty which we have asserted on
            index (int): The index of the assertion to reveal
            nonce (str): Secret nonce used to reveal assertion
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            metadata (str): Optional metadata
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        assert(chain == 'home' or chain == 'side')
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        uri = '{0}/bounties/{1}/assertions/{2}/reveal'.format(
            self.polyswarmd_uri, guid, index)
        reveal = {
            'nonce': nonce,
            'verdicts': verdicts,
            'metadata': metadata,
        }

        params = self.params
        params['chain'] = chain
        async with self.__session.post(uri, params=self.params, json=reveal) as response:
            response = await response.json()
        logging.debug('POST /bounties/%s/assertions/%s/reveal?chain=%s: %s', guid, index, chain, response)
        if not check_response(response):
            return []

        response = await self.post_transactions(response['result']['transactions'], chain)
        if not check_response(response):
            return []

        try:
            return response['result']['reveals']
        except:
            logging.warning('expected reveal, got: %s', response)
            return []


    async def post_vote(self, guid, verdicts, valid_bloom, chain='home'):
        """Post a bounty to polyswarmd

        Args:
            guid (str): The bounty which we are voting on
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            valid_bloom (bool): Is the bloom filter reported by the bounty poster valid
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        assert(chain == 'home' or chain == 'side')
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        uri = '{0}/bounties/{1}/vote'.format(self.polyswarmd_uri, guid)
        vote = {
            'verdicts': verdicts,
            'valid_bloom': valid_bloom,
        }

        params = self.params
        params['chain'] = chain
        async with self.__session.post(uri, params=self.params, json=vote) as response:
            response = await response.json()
        logging.debug('POST /bounties/%s/vote?chain=%s: %s', guid, chain, response)
        if not check_response(response):
            return []

        response = await self.post_transactions(response['result']['transactions'], chain)
        if not check_response(response):
            return []

        try:
            return response['result']['verdicts']
        except:
            logging.warning('expected verdicts, got: %s', response)
            return []


    async def settle_bounty(self, guid, chain='home'):
        """Settle a bounty via polyswarmd

        Args:
            guid (str): The bounty which we are settling
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        assert(chain == 'home' or chain == 'side')
        if self.__session is None or self.__session.closed:
            raise Exception('Not running')

        uri = '{0}/bounties/{1}/settle'.format(
            self.polyswarmd_uri, guid)

        params = self.params
        params['chain'] = chain
        async with self.__session.post(uri, params=self.params) as response:
            response = await response.json()
        logging.debug('POST /bounties/%s/settle?chain=%s: %s', guid, chain, response)
        if not check_response(response):
            return Nonce

        response = await self.post_transactions(response['result']['transactions'], chain)
        if not check_response(response):
            return []

        try:
            return response['result']['transfers']
        except:
            logging.warning('expected transfer, got: %s', response)
            return []


    async def listen_for_events(self, chain='home'):
        """Listen for events via websocket connection to polyswarmd
        """
        assert(chain == 'home' or chain == 'side')
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
                    results = await self.on_new_block.run(number=number, chain=chain)
                    if results:
                        logging.info('Block results on chain %s: %s', chain, results)

                    results = await self.__handle_scheduled_events(number)
                    if results:
                        logging.info('Scheduled event results on chain %s: %s', chain, results)
                elif event['event'] == 'bounty':
                    data = event['data']
                    logging.info('Received bounty on chain %s: %s', chain, data)
                    results = await self.on_new_bounty.run(**data, chain=chain)
                    if results:
                        logging.info('Bounty resultson chain %s: %s', chain, results)
                elif event['event'] == 'assertion':
                    data = event['data']
                    logging.info('Received assertion on chain %s: %s', chain, data)
                    results = await self.on_new_assertion.run(**data, chain=chain)
                    if results:
                        logging.info('Assertion results on chain %s: %s', chain, results)
                elif event['event'] == 'reveal':
                    data = event['data']
                    logging.info('Received reveal on chain %s: %s', chain, data)
                    results = await self.on_reveal_assertion.run(**data, chain=chain)
                    if results:
                        logging.info('Reveal results on chain %s: %s', chain, results)
                elif event['event'] == 'verdict':

                    data = event['data']
                    logging.info('Received verdict on chain %s: %s', chain, data)
                    results = await self.on_new_verdict.run(**data, chain=chain)
                    if results:
                        logging.info('Verdict results on chain %s: %s', chain, results)
                elif event['event'] == 'quorum':
                    data = event['data']
                    logging.info('Received quorum on chain %s: %s', chain, data)
                    results = await self.on_quorum_reached.run(**data, chain=chain)
                    if results:
                        logging.info('Quorum results on chain %s: %s', chain, results)
                elif event['event'] == 'settled_bounty':
                    data = event['data']
                    logging.info('Received settled bounty on chain %s: %s', chain, data)
                    results = await self.on_settled_bounty.run(**data, chain=chain)
                    if results:
                        logging.info('Settle bounty results on chain %s: %s', chain, results)
                elif event['event'] == 'initialized_channel':
                    data = event['data']
                    logging.info('Received initialized_channel: %s', data)
                    results = await self.on_initialized_channel.run(**data, chain=chain)
                    if results:
                        logging.info('Initialized channel results: %s', results)
