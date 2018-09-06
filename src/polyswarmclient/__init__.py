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

    return False


class Client(object):
    def __init__(self, polyswarmd_addr, keyfile, password, api_key=None, tx_error_fatal=False, insecure_transport=False):
        if api_key and insecure_transport:
            raise ValueError('Refusing to send API key over insecure transport')

        protocol = 'http://' if insecure_transport else 'https://'
        self.polyswarmd_uri = protocol + polyswarm_addr

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
            'side': events.Schedule(),
        }

        self.bounty_parameters = {}
        self.staking_parameters = {}

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


    def run(self, event_loop = None):
        """Run this microengine
        """
        if event_loop is None:
            event_loop = asyncio.get_event_loop()

        event_loop.run_until_complete(self.run_task())


    async def run_task(self):
       if self.api_key and not self.polyswarmd_uri.startswith('https://'):
            raise Exception('Refusing to send API key over insecure transport')

        self.params = {'account': self.account} if not self.api_key else {}
        headers = {'Authorization': self.api_key} if self.api_key else {}
        async with aiohttp.ClientSession(headers=headers) as self.__session:
            self.bounty_parameters['home'] = await self.get_bounty_parameters('home')
            self.bounty_parameters['side'] = await self.get_bounty_parameters('side')

            self.staking_parameters['home'] = await self.get_staking_parameters('home')
            self.staking_parameters['side'] = await self.get_staking_parameters('side')

            await self.on_run.run()
            await asyncio.gather(self.listen_for_events('home'), self.listen_for_events('side'))


    def schedule(self, expiration, event, chain='home'):
        """Schedule an event to execute on a particular block

        Args:
            expiration (int): Which block to execute on
            event (Event): Event to trigger on expiration block
            chain (str): Which chain to operate on
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        self.__schedule[chain].put(expiration, event)


    async def __handle_scheduled_events(self, number, chain='home'):
        """Perform scheduled events when a new block is reported

        Args:
            number (int): The current block number reported from polyswarmd
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        ret = []
        while self.__schedule[chain].peek() and self.__schedule[chain].peek()[0] < number:
            exp, task = self.__schedule[chain].get()
            if isinstance(task, events.RevealAssertion):
                ret.append(await self.on_reveal_assertion_due.run(bounty_guid=task.guid, index=task.index, nonce=task.nonce,
                    verdicts=task.verdicts, metadata=task.metadata, chain=chain))
            elif isinstance(task, events.SettleBounty):
                ret.append(await self.on_settle_bounty_due.run(bounty_guid=task.guid, chain=chain))
            elif isinstance(task, events.VoteOnBounty):
                ret.append(await self.on_vote_on_bounty_due.run(bounty_guid=task.guid, verdicts=task.verdicts,
                    valid_bloom=task.valid_bloom, chain=chain))

        return ret


    async def get_bounty_parameters(self, chain='home'):
        """Get bounty parameters from polyswarmd

        Args:
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing bounty parameters
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

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
            logging.error('Expected bounty parameters, got: %s', response)
            return None


    async def get_staking_parameters(self, chain='home'):
        """Get staking parameters from polyswarmd

        Args:
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing staking parameters
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = '{0}/staking/parameters'.format(self.polyswarmd_uri)

        params = self.params
        params['chain'] = chain
        async with self.__session.get(uri, params=params) as response:
            response = await response.json()
        logging.debug('GET /staking/parameters?chain=%s: %s', chain, response)
        if not check_response(response):
            return None

        try:
            return response['result']
        except:
            logging.error('Expected staking parameters, got: %s', response)
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
            raise Exception('not running')

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
            raise xception('Not running')

        if not is_valid_ipfs_uri(ipfs_uri):
            return None

        uri = '{0}/artifacts/{1}'.format(self.polyswarmd_uri, ipfs_uri)
        params = self.params
        async with self.__session.get(uri, params=self.params) as response:
            response = await response.json()
        logging.debug('GET /artifacts/%s: %s', ipfs_uri, response)
        if not check_response(response):
            return []

        return [(a['name'], a['hash']) for a in response.get('result', {})]


    async def calculate_bloom(self, ipfs_uri):
        """Calculate bloom filter for a set of artifacts

        Args:
            ipfs_uri (str): IPFS URI for the artifact set
        Returns:
            Bloom filter value for the artifact set
        """
        artifacts = await self.list_artifacts(ipfs_uri)
        bf = bloom.BloomFilter()
        for _, h in artifacts:
            bf.add(h.encode('utf-8'))

        return int(bf)


    async def post_transactions(self, transactions, chain='home'):
        """Post a set of (signed) transactions to Ethereum via polyswarmd, parsing the emitted events

        Args:
            transactions (List[Transaction]): The transactions to sign and post
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        signed = []
        for tx in transactions:
            s = w3.eth.account.signTransaction(tx, self.priv_key)
            raw = bytes(s['rawTransaction']).hex()
            signed.append(raw)

        uri = '{0}/transactions'.format(self.polyswarmd_uri)

        params = self.params
        params['chain'] = chain
        async with self.__session.post(uri, params=self.params, json={'transactions': signed}) as response:
            response = await response.json()
        logging.debug('POST /transactions?chain=%s: %s', chain, response)
        if self.tx_error_fatal and 'errors' in response.get('result', {}):
            logging.error('Received fatal transaction error: %s', response)
            sys.exit(1)

        return response


    async def post_staking_deposit(self, amount, chain='home', base_nonce=None):
        """Post a deposit to the staking contract

        Args:
            amount (int): The amount to stake
            chain (str): Which chain to operate on
            base_nonce (int): Base nonce to use, automatically calculated if None
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = '{0}/staking/deposit'.format(self.polyswarmd_uri)
        bounty = {
            'amount': str(amount),
        }

        params = self.params
        params['chain'] = chain
        if base_nonce is not None:
            params['base_nonce'] = base_nonce
        async with self.__session.post(uri, params=self.params, json=bounty) as response:
            response = await response.json()
        logging.debug('POST /staking/deposit?chain=%s: %s', chain, response)
        if not check_response(response):
            return []

        response = await self.post_transactions(response['result']['transactions'], chain)
        if not check_response(response):
            return []

        try:
            return response['result']['deposits']
        except:
            logging.error('Expected deposit, got: %s', response)
            return []


    async def post_staking_withdraw(self, amount, chain='home', base_nonce=None):
        """Post a withdrawal to the staking contract

        Args:
            amount (int): The amount to withdraw
            chain (str): Which chain to operate on
            base_nonce (int): Base nonce to use, automatically calculated if None
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = '{0}/staking/withdraw'.format(self.polyswarmd_uri)
        bounty = {
            'amount': str(amount),
        }

        params = self.params
        params['chain'] = chain
        if base_nonce is not None:
            params['base_nonce'] = base_nonce
        async with self.__session.post(uri, params=self.params, json=bounty) as response:
            response = await response.json()
        logging.debug('POST /staking/withdraw?chain=%s: %s', chain, response)
        if not check_response(response):
            return []

        response = await self.post_transactions(response['result']['transactions'], chain)
        if not check_response(response):
            return []

        try:
            return response['result']['withdrawals']
        except:
            logging.error('Expected withdrawal, got: %s', response)
            return []


    async def get_bounty(self, guid, chain='home'):
        """Get a bounty from polyswarmd

        Args:
            guid (str): GUID of the bounty to retrieve
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing bounty details
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = '{0}/bounties/{1}'.format(self.polyswarmd_uri, guid)

        params = self.params
        params['chain'] = chain
        async with self.__session.get(uri, params=self.params) as response:
            response = await response.json()
        logging.debug('GET /bounties/%s?chain=%s: %s', guid, chain, response)
        if not check_response(response):
            return []

        try:
            return response['result']
        except:
            logging.error('Expected bounty, got: %s', response)
            return []


    async def post_bounty(self, amount, uri, duration, chain='home', base_nonce=None):
        """Post a bounty to polyswarmd

        Args:
            amount (int): The amount to put up as a bounty
            uri (str): URI of artifacts
            duration (int): Number of blocks to accept new assertions
            chain (str): Which chain to operate on
            base_nonce (int): Base nonce to use, automatically calculated if None
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = '{0}/bounties'.format(self.polyswarmd_uri)
        bounty = {
            'amount': str(amount),
            'uri': uri,
            'duration': duration,
        }

        params = self.params
        params['chain'] = chain
        if base_nonce is not None:
            params['base_nonce'] = base_nonce
        async with self.__session.post(uri, params=self.params, json=bounty) as response:
            response = await response.json()
        logging.debug('POST /bounties?chain=%s: %s', chain, response)
        if not check_response(response):
            return []

        response = await self.post_transactions(response['result']['transactions'], chain)
        if not check_response(response):
            return []

        try:
            return response['result']['bounties']
        except:
            logging.error('Expected bounty, got: %s', response)
            return []


    async def get_assertion(self, bounty_guid, index, chain='home'):
        """Get an assertion from polyswarmd

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the assertion from
            index (int): Index of the assertion
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing assertion details
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = '{0}/bounties/{1}/assertions/{2}'.format(self.polyswarmd_uri, bounty_guid, index)

        params = self.params
        params['chain'] = chain
        async with self.__session.get(uri, params=self.params) as response:
            response = await response.json()
        logging.debug('GET /bounties/%s/assertions/%s?chain=%s: %s', bounty_guid, index, chain, response)
        if not check_response(response):
            return []

        try:
            return response['result']
        except:
            logging.error('Expected assertion, got: %s', response)
            return []


    async def post_assertion(self, guid, bid, mask, verdicts, chain='home', base_nonce=None):
        """Post an assertion to polyswarmd

        Args:
            guid (str): The bounty to assert on
            bid (int): The amount to bid
            mask (List[bool]): Which artifacts in the bounty to assert on
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            chain (str): Which chain to operate on
            base_nonce (int): Base nonce to use, automatically calculated if None
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = '{0}/bounties/{1}/assertions'.format(
            self.polyswarmd_uri, guid)
        assertion = {
            'bid': str(bid),
            'mask': mask,
            'verdicts': verdicts,
        }

        params = self.params
        params['chain'] = chain
        if base_nonce is not None:
            params['base_nonce'] = base_nonce
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
            logging.error('Expected assertion, got: %s', response)
            return None, []


    async def post_reveal(self, guid, index, nonce, verdicts, metadata, chain='home', base_nonce=None):
        """Post an assertion reveal to polyswarmd

        Args:
            guid (str): The bounty which we have asserted on
            index (int): The index of the assertion to reveal
            nonce (str): Secret nonce used to reveal assertion
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            metadata (str): Optional metadata
            chain (str): Which chain to operate on
            base_nonce (int): Base nonce to use, automatically calculated if None
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = '{0}/bounties/{1}/assertions/{2}/reveal'.format(
            self.polyswarmd_uri, guid, index)
        reveal = {
            'nonce': nonce,
            'verdicts': verdicts,
            'metadata': metadata,
        }

        params = self.params
        params['chain'] = chain
        if base_nonce is not None:
            params['base_nonce'] = base_nonce
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
            logging.error('Expected reveal, got: %s', response)
            return []


    async def post_vote(self, guid, verdicts, valid_bloom, chain='home', base_nonce=None):
        """Post a bounty to polyswarmd

        Args:
            guid (str): The bounty which we are voting on
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            valid_bloom (bool): Is the bloom filter reported by the bounty poster valid
            chain (str): Which chain to operate on
            base_nonce (int): Base nonce to use, automatically calculated if None
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = '{0}/bounties/{1}/vote'.format(self.polyswarmd_uri, guid)
        vote = {
            'verdicts': verdicts,
            'valid_bloom': valid_bloom,
        }

        params = self.params
        params['chain'] = chain
        if base_nonce is not None:
            params['base_nonce'] = base_nonce
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
            logging.error('Expected verdicts, got: %s', response)
            return []


    async def settle_bounty(self, guid, chain='home', base_nonce=None):
        """Settle a bounty via polyswarmd

        Args:
            guid (str): The bounty which we are settling
            chain (str): Which chain to operate on
            base_nonce (int): Base nonce to use, automatically calculated if None
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
        if self.__session is None or self.__session.closed:
            raise Exception('not running')

        uri = '{0}/bounties/{1}/settle'.format(
            self.polyswarmd_uri, guid)

        params = self.params
        params['chain'] = chain
        if base_nonce is not None:
            params['base_nonce'] = base_nonce
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
            logging.error('Expected transfer, got: %s', response)
            return []


    async def listen_for_events(self, chain='home'):
        """Listen for events via websocket connection to polyswarmd

        Args:
            chain (str): Which chain to operate on
        """
        if chain != 'home' and chain != 'side':
            raise ValueError('chain parametermust be "home" or "side"')
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
                        logging.info('Bounty results on chain %s: %s', chain, results)
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
