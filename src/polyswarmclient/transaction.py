import logging
import uuid
from abc import ABCMeta, abstractmethod

from eth_abi import decode_abi, decode_single
from eth_abi.exceptions import InsufficientDataBytes
from hexbytes import HexBytes
from web3 import Web3

from polyswarmclient.utils import bool_list_to_int, int_to_bool_list, calculate_commitment, exit

logger = logging.getLogger(__name__)  # Initialize logger

NCT_APPROVE_SIG_HASH = '095ea7b3'
NCT_TRANSFER_SIG_HASH = 'a9059cbb'
POST_BOUNTY_SIG_HASH = '9b1cdad4'
POST_ASSERTION_SIG_HASH = '9b3544f6'
REVEAL_ASSERTION_SIG_HASH = 'f8f32de6'
VOTE_SIG_HASH = '27028aae'
SETTLE_SIG_HASH = '5592d687'
STAKE_DEPOSIT_SIG_HASH = 'b6b55f25'
STAKE_WITHDRAWAL_SIG_HASH = '2e1a7d4d'


class SimplifiedTransaction():
    """
    This is a simplification of the transaction object returned by polyswarmd.
    The signature hash (first 4 bytes of input data) has been separated from the rest of the data.
    """

    def __init__(self, to, value, signature_hash, data):
        self.to = to
        self.value = value
        self.signature_hash = signature_hash
        self.data = data

    @classmethod
    def simplify(cls, transaction):
        """
        Turn a regular transaction into a SimplifiedTransaction

        Args:
            transaction (dict): Transaction to be simplified
        Returns:
            (SimplifiedTransaction): If all fields exist, returns a SimplifiedTransaction. None otherwise
        """
        w3 = Web3()
        transaction_data = transaction.get('data')
        transaction_to = transaction.get('to')
        value = transaction.get('value')
        if transaction_data is None or transaction_to is None or value is None:
            return None
        byte_data = bytes(HexBytes(transaction_data))
        sig = byte_data[:4]
        data = bytes(HexBytes(byte_data[4:]))
        to = w3.toChecksumAddress(transaction_to)
        return cls(to, value, sig, data)


class AbstractTransactionVerifier(metaclass=ABCMeta):
    """
    This verifier is used to verify the details of a single transaction.
    It decodes the input data into a tuple, and provides some helpers.

    Call verify with a transaction to compare it against a known definition
    """

    def __init__(self, account):
        self.w3 = Web3()
        self.account = account

    def guid_as_string(self, guid):
        return str(uuid.UUID(int=int(guid), version=4))

    def verify(self, transaction):
        abi = self.get_abi()
        try:
            if len(abi) == 1:
                data = decode_single(abi[0], transaction.data)
            else:
                data = decode_abi(abi, transaction.data)
        except InsufficientDataBytes:
            logger.error('Transaction did not match expected input data')
            return False

        return self.verify_transaction(transaction.to, transaction.value, transaction.signature_hash, data)

    @abstractmethod
    def verify_transaction(self, to, value, signature_hash, decoded_data):
        """
        Called when a list of transactions were returned from polyswarmd.
        This function will verify the transactions, and determines if the transactions are expected.

        Args:
            to (str): Address of recipient
            value (int): Value of transaction (Eth)
            signature_hash (bytes): First four bytes of hash of function signature
            decoded_data: Arguments decoded from transaction
        Returns:
            True if valid and expected
        """
        raise NotImplementedError('Verify is not implemented')

    @abstractmethod
    def get_abi(self):
        """
        Called to get the abi breakdown for decoding the transaction input data

        Returns:
            a list of types that match the parameters for the contract function to decode
        """
        raise NotImplementedError('Get abi is not implemented')


class AbstractTransaction(metaclass=ABCMeta):
    """
    Used to verify groups of transactions that make up a specific action.
    For instance, when approving some funds to move, and calling a contract function that will consumer them.

    Call verify to compare a list of transactions.
    """
    def __init__(self, client, verifiers):
        """
        Initialize a group verifier

        Args:
            verifiers (list): Ordered verifiers for each transaction
        """
        self.client = client
        self.verifiers = verifiers

    async def send(self, chain, tries=5, api_key=None):
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

        while tries > 0:
            tries -= 1

            success, result = await self.client.make_request('POST',
                                                             self.get_path(),
                                                             chain,
                                                             json=self.get_body(),
                                                             send_nonce=True,
                                                             api_key=api_key,
                                                             tries=1)
            if not success or 'transactions' not in result:
                logger.error('Expected transactions, received', extra={'extra': result})
                continue

            # Keep around any extra data from the first request, such as nonce for assertion
            transactions = result.get('transactions', [])

            if not self.verify(transactions):
                logger.error("Transactions did not match expectations for the given request.",
                             extra={'extra': transactions})
                if self.client.tx_error_fatal:
                    exit(1)
                return False, {}

            if 'transactions' in result:
                del result['transactions']

            nonce_manager = self.client.nonce_manager[chain]
            nonces = await nonce_manager.next(amount=len(transactions))
            transactions = [self.client.replace_nonce(nonces[i], transaction) for i, transaction in enumerate(transactions)]
            tx_result = await self.client.post_transactions(transactions, chain, api_key=api_key)
            await nonce_manager.finished()
            has_required = self.has_required_event(tx_result)
            errors = tx_result.get('errors', [])
            nonce_error = False
            for e in errors:
                if 'invalid transaction error' in e.lower():
                    nonce_error = True
                    break

                if 'transaction failed at block' in e.lower():
                    logger.error('Transaction failed due to incorrect parameters or missed window, not retrying')
                    if not has_required:
                        return False, {}

            if nonce_error:
                logger.error('Nonce desync detected, resyncing nonce and retrying')
                nonce_manager.mark_update_nonce()
                if not has_required:
                    continue

            return True, {**result, **tx_result}

        return False, {}

    @abstractmethod
    def has_required_event(self, transaction_events):
        """
        Checks the list for a given transaction.
        Useful for many transactions, as they are actually multiple transactions
        In the event one fails, but the needed one succeeds, this will return True

        Returns:
            True if the required event was in the list, false otherwise
        """
        raise NotImplementedError('has_required_event not implemented')

    @abstractmethod
    def get_path(self):
        """
        Get the path to build this transaction

        Returns:
            Polyswarmd path to get the transaction data
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

        simplified = [SimplifiedTransaction.simplify(tx) for tx in transactions]
        return all([v.verify(tx) for v, tx in zip(self.verifiers, simplified)])


class NctApproveVerifier(AbstractTransactionVerifier):
    def __init__(self, amount, account):
        super().__init__(account)
        self.amount = amount

    def get_abi(self):
        return ['address', 'uint256']

    def verify_transaction(self, to, value, signature_hash, decoded_data):
        address, approve_amount = decoded_data
        logger.info('Approve address: %s, amount: %s', address, approve_amount)

        return (signature_hash == HexBytes(NCT_APPROVE_SIG_HASH)
                and value == 0
                and approve_amount == self.amount)


class NctTransferVerifier(AbstractTransactionVerifier):
    def __init__(self, amount, account):
        super().__init__(account)
        self.amount = amount

    def get_abi(self):
        return ['address', 'uint256']

    def verify_transaction(self, to, value, signature_hash, decoded_data):
        address, transfer_amount = decoded_data
        logger.info('Transfer Address: %s, Amount: %s', address, transfer_amount)

        return (signature_hash == HexBytes(NCT_TRANSFER_SIG_HASH)
                and value == 0
                and transfer_amount == self.amount)


class PostBountyVerifier(AbstractTransactionVerifier):
    def __init__(self, amount, artifact_uri, num_artifacts, duration, bloom, account):
        super().__init__(account)
        self.amount = amount
        self.artifact_uri = artifact_uri
        self.num_artifacts = num_artifacts
        self.duration = duration
        self.bloom = bloom

    def get_abi(self):
        return ['uint128', 'uint256', 'string', 'uint256', 'uint256', 'uint256[8]']

    def verify_transaction(self, to, value, signature_hash, data):
        guid, amount, artifact_uri, num_artifacts, duration, bloom = data

        bounty_bloom = 0
        for b in bloom:
            bounty_bloom = bounty_bloom << 256 | int(b)

        logger.info(
            'Post Bounty guid: %s amount: %s, artifact uri: %s, number of artifacts: %s, duration: %s, bloom: %s',
            self.guid_as_string(guid), amount, artifact_uri.decode('utf-8'), num_artifacts, duration, bounty_bloom)
        return (signature_hash == HexBytes(POST_BOUNTY_SIG_HASH)
                and value == 0
                and artifact_uri.decode('utf8') == self.artifact_uri
                and num_artifacts == self.num_artifacts
                and duration == self.duration
                and bounty_bloom == self.bloom
                and amount == self.amount)


class PostAssertionVerifier(AbstractTransactionVerifier):
    def __init__(self, guid, bid, mask, verdicts, nonce, account):
        super().__init__(account)
        self.guid = guid
        self.bid = bid
        self.mask = mask
        self.verdicts = verdicts
        self.nonce = nonce

    def get_abi(self):
        return ['uint128', 'uint256', 'uint256', 'uint256']

    def verify_transaction(self, to, value, signature_hash, data):
        guid, bid, mask, commitment = data

        _, expected_commitment = calculate_commitment(self.account, bool_list_to_int(self.verdicts), nonce=self.nonce)

        logger.info('Post Assertion guid: %s bid: %s, mask: %s, commitment: %s', self.guid_as_string(guid), bid, mask,
                    commitment)

        return (signature_hash == HexBytes(POST_ASSERTION_SIG_HASH)
                and value == 0
                and self.guid_as_string(guid) == self.guid
                and bid == self.bid
                and commitment == expected_commitment
                and int_to_bool_list(mask) == self.mask)

class RevealAssertionVerifier(AbstractTransactionVerifier):
    def __init__(self, guid, index, nonce, verdicts, metadata, account):
        super().__init__(account)
        self.guid = guid
        self.index = index
        self.nonce = nonce
        self.verdicts = verdicts
        self.metadata = metadata

    def get_abi(self):
        return ['uint128', 'uint256', 'uint256', 'uint256', 'string']

    def verify_transaction(self, to, value, signature_hash, data):
        guid, assertion_id, nonce, verdicts, metadata = data

        # If there is a 1 anywhere beyond the length of items we expect, fail it
        if verdicts >> len(self.verdicts) > 0:
            return False

        logger.info('Reveal Assertion guid: %s assertion_id: %s, verdicts: %s, metadata: %s', self.guid_as_string(guid),
                    assertion_id, int_to_bool_list(verdicts), metadata.decode('utf-8'))
        return (signature_hash == HexBytes(REVEAL_ASSERTION_SIG_HASH)
                and value == 0
                and self.guid_as_string(guid) == self.guid
                and assertion_id == self.index
                and int_to_bool_list(verdicts) == self.verdicts
                and metadata.decode('utf-8') == self.metadata
                and nonce == int(self.nonce))


class PostVoteVerifier(AbstractTransactionVerifier):
    def __init__(self, guid, votes, valid_bloom, account):
        super().__init__(account)
        self.guid = guid
        self.votes = votes
        self.valid_bloom = valid_bloom

    def get_abi(self):
        return ['uint128', 'uint256', 'bool']

    def verify_transaction(self, to, value, signature_hash, data):
        guid, votes, valid_bloom = data
        logger.info('Post Vote guid: %s, votes: %s, valid_bloom: %s', self.guid_as_string(guid),
                    int_to_bool_list(votes), valid_bloom)
        return (signature_hash == HexBytes(VOTE_SIG_HASH)
                and value == 0
                and self.guid_as_string(guid) == self.guid
                and int_to_bool_list(votes) == self.votes
                and valid_bloom == self.valid_bloom)


class SettleBountyVerifier(AbstractTransactionVerifier):
    def __init__(self, guid, account):
        super().__init__(account)
        self.guid = guid

    def get_abi(self):
        return ['uint128']

    def verify_transaction(self, to, value, signature_hash, data):
        guid = data
        logger.info('Settle bounty guid: %s', self.guid_as_string(guid))
        return (signature_hash == HexBytes(SETTLE_SIG_HASH)
                and value == 0
                and self.guid_as_string(guid) == self.guid)


class StakingDepositVerifier(AbstractTransactionVerifier):
    def __init__(self, amount, account):
        super().__init__(account)
        self.amount = amount

    def get_abi(self):
        return ['uint256']

    def verify_transaction(self, to, value, signature_hash, data):
        amount = data
        logger.info('Stake Deposit Amount: %s', amount)
        return (signature_hash == HexBytes(STAKE_DEPOSIT_SIG_HASH)
                and value == 0
                and amount == self.amount)


class StakingWithdrawVerifier(AbstractTransactionVerifier):
    def __init__(self, amount, account):
        super().__init__(account)
        self.amount = amount

    def get_abi(self):
        return ['uint256']

    def verify_transaction(self, to, value, signature_hash, data):
        amount = data
        logger.info('Stake Withdraw Amount: %s', amount)
        return (signature_hash == HexBytes(STAKE_WITHDRAWAL_SIG_HASH)
                and value == 0
                and amount == self.amount)
