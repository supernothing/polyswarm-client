import asyncio
import logging
from abc import ABCMeta, abstractmethod

from polyswarmclient.utils import exit

logger = logging.getLogger(__name__)


class NonceManager:
    """Manages the nonce for some Ethereum chain"""

    def __init__(self, client, chain):
        self.base_nonce = 0
        self.client = client
        self.chain = chain

        self.needs_update = True
        self.nonce_lock = asyncio.Lock()
        self.in_progress = 0
        self.in_progress_condition = asyncio.Condition()

    async def acquire(self):
        """Acquires the nonce lock and updates base_nonce if needs_update is set"""
        await self.nonce_lock.acquire()

        if self.needs_update:
            async with self.in_progress_condition:
                # The wait inside here will release this lock, allowing finished() to work
                await self.in_progress_condition.wait_for(self.all_finished)

            # Wait for nonce to settle, can't rely on pending tx count
            last_nonce = -1
            while True:
                nonce = await self.client.get_base_nonce(self.chain)
                if nonce is not None and nonce == last_nonce:
                    break

                last_nonce = nonce
                await asyncio.sleep(1)

            if nonce is not None:
                self.base_nonce = nonce

            logger.warning('Updated nonce to %s on %s', nonce, self.chain)
            self.needs_update = False

    def all_finished(self):
        """Check that all tasks have finished"""
        return self.in_progress == 0

    async def finished(self):
        """Mark that some in-progress transaction finished on polyswarmd"""
        async with self.in_progress_condition:
            self.in_progress -= 1
            logger.debug('Tx resolved, in_progress: %s', self.in_progress)

            self.in_progress_condition.notify()

    async def reserve(self, amount=1):
        """Grab the next amount nonces.

        Args:
            amount (int): amount of sequential nonces to be claimed
        Returns
            (list[int]): a list of nonces to use
        """
        async with self:
            results = range(self.base_nonce, self.base_nonce + amount)
            self.base_nonce += amount

            # Inside nonce_lock so that there is no way the next acquire could miss an in progress
            async with self.in_progress_condition:
                # Note that a set of nonces is being used
                self.in_progress += 1
                logger.debug('New tx in flight, in_progress: %s', self.in_progress)

        return results

    def mark_update_nonce(self):
        """
        Call this when the nonce is out of sync.
        This sets the update flag to true.
        The next acquire after being set will trigger an update
        """
        self.needs_update = True

    async def __aenter__(self):
        await self.acquire()

    async def __aexit__(self, exc_type, exc, tb):
        self.nonce_lock.release()


class AbstractTransaction(metaclass=ABCMeta):
    """Used to verify and post groups of transactions that make up a specific action.

    For instance, when approving some funds to move, and calling a contract function that will consumer them.
    """

    def __init__(self, client, verifiers):
        """Initialize a transaction

        Args:
            client (Client): Client object used to post transactions
            verifiers (list): Ordered verifiers for each transaction
        """
        self.client = client
        self.verifiers = verifiers

    async def send(self, chain, tries=2, api_key=None):
        """Make a transaction generating request to polyswarmd, then sign and post the transactions

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
            tries (int): Number of times to retry before giving up
        Returns:
            (bool, obj): Tuple of boolean representing success, and response JSON parsed from polyswarmd
        """
        if api_key is None:
            api_key = self.client.api_key

        # Ensure we try at least once
        tries = max(tries, 1)

        success, result = await self.client.make_request('POST',
                                                         self.get_path(),
                                                         chain,
                                                         json=self.get_body(),
                                                         send_nonce=True,
                                                         api_key=api_key,
                                                         tries=tries)
        if not success or 'transactions' not in result:
            logger.error('Expected transactions, received', extra={'extra': result})
            return False, result

        transactions = result.get('transactions', [])
        if not self.verify(transactions):
            logger.error("Transactions did not match expectations for the given request.",
                         extra={'extra': transactions})
            if self.client.tx_error_fatal:
                exit(1)
            return False, {}

        # Keep around any extra data from the first request, such as nonce for assertion
        if 'transactions' in result:
            del result['transactions']

        txhashes = []
        post_errors = []
        get_errors = []

        # Step one: Update nonces, sign then post transactions
        replace_nonce = True
        while tries > 0:
            tries -= 1

            # replace_nonce is True on first iteration and then after if nonce error occurs
            nonce_manager = self.client.nonce_managers[chain]
            if replace_nonce:
                nonces = await nonce_manager.reserve(amount=len(transactions))
                for i, transaction in enumerate(transactions):
                    transaction['nonce'] = nonces[i]

            signed_txs = self.client.sign_transactions(transactions)
            raw_signed_txs = [bytes(tx['rawTransaction']).hex() for tx in signed_txs]
            success, results = await self.__post_transactions(raw_signed_txs, chain, api_key)
            results = [] if results is None else results

            if replace_nonce:
                await nonce_manager.finished()
                replace_nonce = False

            if len(results) != len(signed_txs):
                logger.warning('Transaction result length mismatch')

            txhashes = []
            post_errors = []
            for tx, result in zip(signed_txs, results):
                txhash = bytes(tx['hash']).hex()
                message = result.get('message', '')
                is_error = result.get('is_error', False)

                # Known transaction errors seem to be a geth issue, don't retransmit in this case
                if is_error and 'known transaction' not in message.lower():
                    post_errors.append(message)
                else:
                    txhashes.append(txhash)

            if txhashes:
                if post_errors:
                    logger.warning('Transaction errors detected but some succeeded, fetching events',
                                   extra={'extra': post_errors})

                break

            # Indicates a nonce error, resync nonces and retry
            if any(['invalid transaction error' in e.lower() for e in post_errors]):
                logger.error('Nonce desync detected, resyncing and trying again')
                nonce_manager.mark_update_nonce()
                replace_nonce = True

        if not txhashes:
            return False, {'errors': post_errors + get_errors}

        # Step two: At least one transaction was submitted successfully, get and verify the events it generated
        tries += 1
        while tries > 0:
            tries -= 1

            success, results = await self.__get_transactions(txhashes, chain, api_key)

            get_errors = results.get('errors', [])
            has_required = self.has_required_event(results)

            # Check to see if we failed to retrieve some receipts, retry the fetch if so
            if not has_required and any(['receipt' in e.lower() for e in get_errors]):
                logger.warning('Error fetching some receipts, retrying')
                continue

            if any(['transaction failed' in e.lower() for e in get_errors]):
                logger.error('Transaction failed due to bad parameters, not retrying', extra={'extra': get_errors})
                break

            # Combine our error output, but this is a success
            results['errors'] = post_errors + get_errors
            return has_required, results

        return False, {'errors': post_errors + get_errors}

    async def __post_transactions(self, transactions, chain, api_key):
        """Post a set of (signed) transactions to Ethereum via polyswarmd, parsing the emitted events

        Args:
            transactions (List[Transaction]): The transactions to sign and post
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing transaction status
        """
        success, results = await self.client.make_request('POST', '/transactions', chain,
                                                          json={'transactions': transactions}, api_key=api_key, tries=1)

        if not success:
            # Known transaction errors seem to be a geth issue, don't spam log about it
            all_known_tx_errors = results is not None and \
                                  all(['known transaction' in r.get('message', '') for r in results if
                                       r.get('is_error')])

            if self.client.tx_error_fatal:
                logger.error('Received fatal transaction error during post', extra={'extra': results})
                exit(1)
            elif not all_known_tx_errors:
                logger.error('Received transaction error during post', extra={'extra': results})

        return success, results

    async def __get_transactions(self, txhashes, chain, api_key):
        """Get generated events or errors from receipts for a set of txhashes

        Args:
            txhashes (List[str]): The txhashes of the receipts to process
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        success, results = await self.client.make_request('GET', '/transactions', chain,
                                                          json={'transactions': txhashes}, api_key=api_key, tries=1)
        if not success:
            if self.client.tx_error_fatal:
                logger.error('Received fatal transaction error during get', extra={'extra': results})
                exit(1)
            else:
                logger.error('Received transaction error during get', extra={'extra': results})

        return success, results

    @abstractmethod
    def has_required_event(self, transaction_events):
        """Checks for existence of events in transaction logs, ensuring successful completion

        Returns:
            True if the required event was in the list, false otherwise
        """
        raise NotImplementedError('has_required_event not implemented')

    @abstractmethod
    def get_path(self):
        """Get the path of the route to build this transaction

        Returns:
            str: Polyswarmd path to get the transaction data
        """
        raise NotImplementedError('get path is not implemented')

    @abstractmethod
    def get_body(self):
        """
        Build the payload to send to polyswarmd
        Returns:
            Dict payload
        """
        raise NotImplementedError('get body is not implemented')

    def verify(self, transactions):
        """Check the given transactions against known expectations

        Args:
            transactions (list) - A list of transactions from polyswarmd
        Returns:
            (bool): True if transactions match expectations. False otherwise
        """
        if len(transactions) != len(self.verifiers):
            return False

        return all([v.verify(tx) for v, tx in zip(self.verifiers, transactions)])
