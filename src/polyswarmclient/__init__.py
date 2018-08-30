import aiohttp
import asyncio
import base58
import json
import logging
import sys
import websockets

from web3 import Web3
w3 = Web3()

from events import Callback, Schedule, RevealAssertion, SettleBounty

# These values come from the BountyRegistry contract
MINIMUM_BID = 62500000000000000
ARBITER_VOTE_WINDOW = 25
ASSERTION_REVEAL_WINDOW = 100


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

        with open(keyfile, 'r') as f:
            self.priv_key = w3.eth.account.decrypt(f.read(), password)

        self.account = w3.eth.account.privateKeyToAccount(
            self.priv_key).address
        logging.info('Using account: %s', self.account)

        self.schedule = Schedule()
        self.session = None

        # Events from polyswarmd
        self.on_new_block = Callback()
        self.on_new_bounty = Callback()
        self.on_new_assertion = Callback()
        self.on_reveal_assertion = Callback()
        self.on_new_verdict = Callback()
        self.on_quorum = Callback()
        self.on_settled_bounty = Callback()
        self.on_initialized_channel = Callback()

        # Events scheduled on block deadlines
        self.on_reveal_assertion_due = Callback()
        self.on_settle_bounty_due = Callback()


    def run(self, event_loop = None):
        """Run this microengine
        """
        if event_loop is None:
            event_loop = asyncio.get_event_loop()
        event_loop.run_until_complete(listen_for_events(self))


    async def get_artifact(self, ipfs_uri, index):
        """Retrieve an artifact from IPFS via polyswarmd

        Args:
            ipfs_uri (str): IPFS hash of the artifact to retrieve
            index (int): Index of the sub artifact to retrieve
        Returns:
            (bytes): Content of the artifact
        """
        if self.session is None:
            raise Exception('Not running')

        if not is_valid_ipfs_uri(ipfs_uri):
            return None

        uri = '{0}/artifacts/{1}/{2}'.format(
            self.polyswarmd_uri, ipfs_uri, index)
        async with self.session.get(uri) as response:
            if response.status == 200:
                return await response.read()

            return None


    # Async iterator helper class
    class __GetArtifacts(object):
        def __init__(self, client, session, ipfs_uri):
            self.i = 0
            self.client = client
            self.session = session
            self.ipfs_uri = ipfs_uri

        async def __aiter__(self):
            return self

        async def __anext__(self):
            i = self.i
            self.i += 1

            if i < 256:
                content = await self.client.get_artifact(self.session, self.ipfs_uri, i)
                if content:
                    return content

            raise StopAsyncIteration


    def get_artifacts(self, ipfs_uri):
        if self.session is None:
            raise Exception('Not running')

        return Client.__GetArtifacts(self, self.session, ipfs_uri)


    async def post_transactions(self, transactions):
        """Post a set of (signed) transactions to Ethereum via polyswarmd, parsing the emitted events

        Args:
            transactions (List[Transaction]): The transactions to sign and post
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if self.session is None:
            raise Exception('Not running')

        signed = []
        for tx in transactions:
            s = w3.eth.account.signTransaction(tx, self.priv_key)
            raw = bytes(s['rawTransaction']).hex()
            signed.append(raw)

        uri = '{0}/transactions'.format(self.polyswarmd_uri)

        async with self.session.post(
                uri, json={'transactions': signed}) as response:
            j = await response.json()
            if self.tx_error_fatal and 'errors' in j.get('result', {}):
                logging.error('Received fatal transaction error: %s', j)
                sys.exit(1)

            return j


    async def post_bounty(self, amount, uri, duration):
        """Post a bounty to polyswarmd

        Args:
            amount (int): The amount to put up as a bounty
            uri (str): URI of artifacts
            duration (int): Number of blocks to accept new assertions
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if self.session is None:
            raise Exception('Not running')

        uri = '{0}/bounties'.format(self.polyswarmd_uri)
        bounty = {
            'amount': str(amount),
            'uri': uri,
            'duration': duration,
        }

        async with self.session.post(uri, json=bounty) as response:
            response = await response.json()
        if not check_response(response):
            return None, []

        response = await self.post_transactions(response['result']['transactions'])
        if not check_response(response):
            return None, []

        try:
            return nonce, response['result']['bounties']
        except:
            logging.warning('expected bounty, got: %s', response)
            return None, []


    async def post_assertion(self, guid, bid, mask, verdicts):
        """Post an assertion to polyswarmd

        Args:
            guid (str): The bounty to assert on
            bid (int): The amount to bid
            mask (List[bool]): Which artifacts in the bounty to assert on
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if self.session is None:
            raise Exception('Not running')

        uri = '{0}/bounties/{1}/assertions'.format(
            self.polyswarmd_uri, guid)
        assertion = {
            'bid': str(bid),
            'mask': mask,
            'verdicts': verdicts,
        }

        async with self.session.post(uri, json=assertion) as response:
            response = await response.json()
        if not check_response(response):
            return None, []

        nonce = response['result']['nonce']
        response = await self.post_transactions(response['result']['transactions'])
        if not check_response(response):
            return None, []

        try:
            return nonce, response['result']['assertions']
        except:
            logging.warning('expected assertion, got: %s', response)
            return None, []


    async def post_reveal(self, guid, index, nonce, verdicts, metadata):
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
        if self.session is None:
            raise Exception('Not running')

        uri = '{0}/bounties/{1}/assertions/{2}/reveal'.format(
            self.polyswarmd_uri, guid, index)
        reveal = {
            'nonce': nonce,
            'verdicts': verdicts,
            'metadata': metadata,
        }

        async with self.session.post(uri, json=reveal) as response:
            response = await response.json()
        if not check_response(response):
            return None

        response = await self.post_transactions(response['result']['transactions'])
        if not check_response(response):
            return None

        try:
            return response['result']['reveals']
        except:
            logging.warning('expected reveal, got: %s', response)
            return None


    async def post_vote(self, guid, verdicts, valid_bloom):
        """Post a bounty to polyswarmd

        Args:
            guid (str): The bounty which we are voting on
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            valid_bloom (bool): Is the bloom filter reported by the bounty poster valid
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if self.session is None:
            raise Exception('Not running')

        uri = '{0}/bounties/{1}/vote'.format(self.polyswarmd_uri, guid)
        vote = {
            'verdicts': verdicts,
            'valid_bloom': valid_bloom,
        }

        async with self.session.post(uri, json=vote) as response:
            response = await response.json()
        if not check_response(response):
            return None, []

        response = await self.post_transactions(response['result']['transactions'])
        if not check_response(response):
            return None, []

        try:
            return nonce, response['result']['verdicts']
        except:
            logging.warning('expected verdicts, got: %s', response)
            return None, []


    async def settle_bounty(self, guid):
        """Settle a bounty via polyswarmd

        Args:
            guid (str): The bounty which we are settling
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        if self.session is None:
            raise Exception('Not running')

        uri = '{0}/bounties/{1}/settle'.format(
            self.polyswarmd_uri, guid)

        async with self.session.post(uri) as response:
            response = await response.json()
        if not check_response(response):
            return Nonce

        response = await self.post_transactions(response['result']['transactions'])
        if not check_response(response):
            return None

        try:
            return response['result']['transfers']
        except:
            logging.warning('expected transfer, got: %s', response)
            return None


    async def __handle_scheduled_events(self, number):
        """Perform scheduled events when a new block is reported

        Args:
            number (int): The current block number reported from polyswarmd
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        ret = []
        while self.schedule.peek() and self.schedule.peek()[0] < number:
            exp, task = self.schedule_get()
            if isinstance(task, self.RevealAssertion):
                ret.append(await self.on_reveal_assertion_due.run(task.guid, task.index, task.nonce, task.verdicts, task.metadata))
            elif isinstance(task, self.SettleBounty):
                ret.append(await self.on_settle_bounty_due.run(task.guid))

        return ret


    async def listen_for_events(self):
        """Listen for events via websocket connection to polyswarmd
        """
        uri = '{0}/events'.format(self.polyswarmd_uri)

        assert(uri.startswith('http'))
        wsuri = uri.replace('http', 'ws', 1)

        headers = {'Authorization': self.api_key} if self.api_key else {}
        params = {'account': self.account if not self.api_key else {}}
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                self.session = session
                async with websockets.connect(wsuri, extra_headers=headers) as ws:
                    while True:
                        event = json.loads(await ws.recv())
                        if event['event'] == 'block':
                            number = event['data']['number']
                            if number % 100 == 0:
                                logging.debug('Block %s', number)
                            results = await self.on_new_block.run(number)
                            if results:
                                logging.info('Block results: %s', results)

                            results = await self.__handle_scheduled_events(number)
                            if results:
                                logging.info('Scheduled event results: %s', results)
                        elif event['event'] == 'bounty':
                            data = event['data']
                            logging.info('Received bounty: %s', data)
                            results = await self.on_new_bounty.run(**data)
                            if results:
                                logging.info('Bounty results: %s', results)
                        elif event['event'] == 'assertion':
                            data = event['data']
                            logging.info('Received assertion: %s', data)
                            results = await self.on_new_assertion.run(**data)
                            if results:
                                logging.info('Assertion results: %s', results)
                        elif event['event'] == 'reveal':
                            data = event['data']
                            logging.info('Received reveal: %s', data)
                            results = await self.on_reveal_assertion.run(**data)
                            if results:
                                logging.info('Reveal results: %s', results)
                        elif event['event'] == 'verdict':
                            data = event['data']
                            logging.info('Received verdict: %s', data)
                            results = await self.on_new_verdict.run(**data)
                            if results:
                                logging.info('Verdict results: %s', results)
                        elif event['event'] == 'quorum':
                            data = event['data']
                            logging.info('Received quorum: %s', data)
                            results = await self.on_quorum.run(**data)
                            if results:
                                logging.info('Quorum results: %s', results)
                        elif event['event'] == 'settled_bounty':
                            data = event['data']
                            logging.info('Received settled bounty: %s', data)
                            results = await self.on_settled_bounty.run(**data)
                            if results:
                                logging.info('Settle bounty results: %s', results)
                        elif event['event'] == 'initialized_channel':
                            data = event['data']
                            logging.info('Received initialized_channel: %s', data)
                            results = await self.on_initialized_channel.run(**data)
                            if results:
                                logging.info('Initialized channel results: %s', results)
            finally:
                self.session = None
