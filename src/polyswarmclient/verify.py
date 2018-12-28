import logging
import rlp
import uuid
from abc import ABCMeta, abstractmethod
from eth_abi import decode_abi, decode_single
from eth_abi.exceptions import InsufficientDataBytes
from web3 import Web3
from hexbytes import HexBytes

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

    def bool_list_to_int(self, bool_list):
        retval = 0
        for b in bool_list:
            retval << 1
            retval += 1 if b else 0

        return retval

    def bytes_to_int(self, value):
        return int.from_bytes(value, byteorder='big')

    def calculate_commitment(self, nonce, verdicts):
        account = int(self.account, 16)
        nonce_hash = self.w3.sha3(int(nonce))
        commitment = self.w3.sha3(self.int_to_bytes(verdicts ^ self.bytes_to_int(nonce_hash) ^ account))
        return self.bytes_to_int(commitment)

    def guid_as_string(self, guid):
        return str(uuid.UUID(int=int(guid), version=4))

    def int_to_bool_list(self, value, length):
        return [value >> i & 1 == 1 for i in range(0, length)]

    def int_to_bytes(self, value):
        h = hex(value)[2:]
        return bytes.fromhex('0' * (64 - len(h)) + h)

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
    def verify_transaction(self, data_tuple, transaction):
        """
        Called when a list of transactions were returned from polyswarmd.
        This function will verify the transactions, and determines if the transactions are expected.

        Args:
            transactions (list): Transactions to be verified before signing and returning to polyswarmd
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

class TransactionGroupVerifier():
    """
    Used to verify groups of transactions that make up a specific action.
    For instance, when approving some funds to move, and calling a contract function that will consumer them.

    Call verify to compare a list of transactions.
    """
    def __init__(self, verifiers):
        """
        Initialize a group verifier

        Args:
            verifiers (list): Ordered verifiers for each transaction
        """
        self.verifiers = verifiers

    def verify(self, transactions, assertion_nonce=None):
        simplified = self.simplify_transactions(transactions)
        if simplified is None or not simplified:
            return False

        return self.verify_transactions(simplified, assertion_nonce)

    def simplify_transactions(self, transactions):
        simplified = []
        for transaction in transactions:
            simple = SimplifiedTransaction.simplify(transaction)
            if simple is None:
                return None

            simplified.append(simple)
        return simplified

    def verify_transactions(self, transactions, assertion_nonce):
        """Check the given transactions against known expectations

        Args:
            transactions (list) - A list of transactions from polyswarmd
            assertion_nonce (string) - The nonce returned after making a request against the assertion route in polyswarmd.
        Returns:
            (bool): True if transactions match expectations. False otherwise
        """
        if len(transactions) != len(self.verifiers):
            return False

        for i, transaction in enumerate(transactions):
            if not self.verifiers[i].verify(transaction):
                return False

        return True

class NctApproveVerifier(AbstractTransactionVerifier):
    def __init__(self, amount, account):
        super().__init__(account)
        self.amount = amount

    def get_abi(self):
        return ['address', 'uint256']

    def verify_transaction(self, to, value, signature_hash, data_tuple):
        address, approve_amount = data_tuple
        logger.info('Approve Address: %s, Amount: %s', address, approve_amount)

        return (signature_hash == HexBytes(NCT_APPROVE_SIG_HASH)
                and value == 0
                and approve_amount == self.amount)

class NctTransferVerifier(AbstractTransactionVerifier):
    def __init__(self, amount, account):
        super().__init__(account)
        self.amount = amount

    def get_abi(self):
        return ['address', 'uint256']

    def verify_transaction(self, to, value, signature_hash, data_tuple):
        address, transfer_amount = data_tuple
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

        logger.info('Post Bounty guid: %s amount: %s, artifact uri: %s, number of artifacts: %s, duration: %s, bloom: %s', self.guid_as_string(guid), amount, artifact_uri.decode('utf-8'), num_artifacts, duration, bounty_bloom)
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

        if self.nonce is None:
            return False
        given_commitment = self.calculate_commitment(self.nonce, self.bool_list_to_int(self.verdicts))

        # If there is a 1 anywhere beyond the length of items we expect, fail it
        if mask >> len(self.mask) > 0:
            return False

        logger.info('Post Assertion guid: %s bid: %s, mask: %s, commitment: %s', self.guid_as_string(guid), bid, mask, commitment)
        return (signature_hash == HexBytes(POST_ASSERTION_SIG_HASH)
                and value == 0
                and self.guid_as_string(guid) == self.guid
                and bid == self.bid
                and commitment == given_commitment
                and self.int_to_bool_list(mask, len(self.mask)) == self.mask)

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

        logger.info('Reveal Assertion guid: %s assertion_id: %s, verdicts: %s, metadata: %s', self.guid_as_string(guid), assertion_id, self.int_to_bool_list(verdicts, len(self.verdicts)), metadata.decode('utf-8'))
        return (signature_hash == HexBytes(REVEAL_ASSERTION_SIG_HASH)
                and value == 0
                and self.guid_as_string(guid) == self.guid
                and assertion_id == self.index
                and self.int_to_bool_list(verdicts, len(self.verdicts)) == self.verdicts
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
        logger.info('Post Vote guid: %s, votes: %s, valid_bloom: %s', self.guid_as_string(guid), self.int_to_bool_list(votes, len(self.votes)), valid_bloom)
        return (signature_hash == HexBytes(VOTE_SIG_HASH)
                and value == 0
                and self.guid_as_string(guid) == self.guid
                and self.int_to_bool_list(votes, len(self.votes)) == self.votes
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

class PostBountyGroupVerifier(TransactionGroupVerifier):
    def __init__(self, amount, bounty_fee, artifact_uri, num_artifacts, duration, bloom, account):
        approve = NctApproveVerifier(amount + bounty_fee, account)
        bounty = PostBountyVerifier(amount, artifact_uri, num_artifacts, duration, bloom, account)
        super().__init__([approve, bounty])

class PostAssertionGroupVerifier(TransactionGroupVerifier):
    def __init__(self, guid, bid, assertion_fee, mask, verdicts, account):
        self.guid = guid
        self.bid = bid
        self.assertion_fee = assertion_fee
        self.mask = mask
        self.verdicts = verdicts
        self.account = account

    def verify_transactions(self, transactions, assertion_nonce=None):
        if len(transactions) != 2:
            return False

        approve = NctApproveVerifier(self.bid + self.assertion_fee, self.account)
        assertion = PostAssertionVerifier(self.guid, self.bid, self.mask, self.verdicts, assertion_nonce, self.account)
        return approve.verify(transactions[0]) and assertion.verify(transactions[1])

class RevealAssertionGroupVerifier(TransactionGroupVerifier):
    def __init__(self, guid, index, nonce, verdicts, metadata, account):
        reveal = RevealAssertionVerifier(guid, index, nonce, verdicts, metadata, account)
        super().__init__([reveal])

class PostVoteGroupVerifier(TransactionGroupVerifier):
    def __init__(self, guid, votes, valid_bloom, account):
        vote = PostVoteVerifier(guid, votes, valid_bloom, account)
        super().__init__([vote])

class SettleBountyGroupVerifier(TransactionGroupVerifier):
    def __init__(self, guid, account):
        settle = SettleBountyVerifier(guid, account)
        super().__init__([settle])

class RelayWithdrawDepositGroupVerifier(TransactionGroupVerifier):
    def __init__(self, amount, account):
        transfer = NctTransferVerifier(amount, account)
        super().__init__([transfer])

class StakeDepositGroupVerifier(TransactionGroupVerifier):
    def __init__(self, amount, account):
        approve = NctApproveVerifier(amount, account)
        deposit = StakingDepositVerifier(amount, account)
        super().__init__([approve, deposit])

class StakeWithdrawGroupVerifier(TransactionGroupVerifier):
    def __init__(self, amount, account):
        withdraw = StakingWithdrawVerifier(amount, account)
        super().__init__([withdraw])
