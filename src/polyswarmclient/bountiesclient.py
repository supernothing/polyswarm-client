import logging

from polyswarmclient import bloom
from polyswarmclient.utils import bool_list_to_int, calculate_commitment
from polyswarmclient.verify import PostVoteGroupVerifier, PostAssertionGroupVerifier, PostBountyGroupVerifier, \
    RevealAssertionGroupVerifier, SettleBountyGroupVerifier

logger = logging.getLogger(__name__)


class BountiesClient(object):
    def __init__(self, client):
        self.__client = client
        self.parameters = {}

    async def get_parameters(self, chain, api_key=None):
        """Get bounty parameters from polyswarmd.

        Args:
            chain (str): Which chain to operate on.
            api_key (str): Override default API key
        Note:
            This function doesn't return anything. It instead stores the bounty parameters
            as parsed JSON in self.parameters[chain].
        """
        success, result = await self.__client.make_request('GET', '/bounties/parameters', chain, api_key=api_key)
        if not success:
            raise Exception('Error retrieving bounty parameters')
        self.parameters[chain] = result

    async def get_artifact_count(self, ipfs_uri, api_key=None):
        """Gets the number of artifacts at the ipfs uri

        Args:
            ipfs_uri (str): IPFS URI for the artifact set
            api_key (str): Override default API key
        Returns:
            Number of artifacts at the uri
        """
        artifacts = await self.__client.list_artifacts(ipfs_uri, api_key=api_key)
        return len(artifacts) if artifacts is not None and artifacts else 0

    async def calculate_bloom(self, ipfs_uri, api_key=None):
        """Calculate bloom filter for a set of artifacts.

        Args:
            ipfs_uri (str): IPFS URI for the artifact set
            api_key (str): Override default API key
        Returns:
            Bloom filter value for the artifact set
        """
        artifacts = await self.__client.list_artifacts(ipfs_uri, api_key=api_key)
        bf = bloom.BloomFilter()
        for _, h in artifacts:
            bf.add(h.encode('utf-8'))

        return int(bf)

    async def get_bloom(self, bounty_guid, chain, api_key=None):
        """
        Get bloom from polyswamrd

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the vote from
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        """
        path = '/bounties/{0}/bloom'.format(bounty_guid)
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected bloom, received', extra={'response': result})
            return None
        return result.get('bloom')

    async def get_bounty(self, guid, chain, api_key=None):
        """Get a bounty from polyswarmd.

        Args:
            guid (str): GUID of the bounty to retrieve
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing bounty details
        """
        path = '/bounties/{0}'.format(guid)
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected bounty, received', extra={'response': result})
            return None

        return result

    async def post_bounty(self, amount, artifact_uri, duration, chain, api_key=None):
        """Post a bounty to polyswarmd.

        Args:
            amount (int): The amount to put up as a bounty
            artifact_uri (str): URI of artifacts
            duration (int): Number of blocks to accept new assertions
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        bounty = {
            'amount': str(amount),
            'uri': artifact_uri,
            'duration': duration,
        }
        bounty_fee = self.parameters[chain]['bounty_fee']
        bloom = await self.calculate_bloom(artifact_uri)
        num_artifacts = await self.get_artifact_count(artifact_uri)
        verifier = PostBountyGroupVerifier(amount, bounty_fee, artifact_uri, num_artifacts, duration, bloom,
                                           self.__client.account)
        success, result = await self.__client.make_request_with_transactions('POST', '/bounties', chain, verifier,
                                                                             json=bounty,
                                                                             api_key=api_key)
        if not success or 'bounties' not in result:
            logger.error('Expected bounty, received', extra={'response': result})

        return result.get('bounties', [])

    async def get_assertion(self, bounty_guid, index, chain, api_key=None):
        """Get an assertion from polyswarmd.

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the assertion from
            index (int): Index of the assertion
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing assertion details
        """
        path = '/bounties/{0}/assertions/{1}'.format(bounty_guid, index)
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected assertion, received', extra={'response': result})
            return None

        return result

    async def post_assertion(self, bounty_guid, bid, mask, verdicts, chain, api_key=None):
        """Post an assertion to polyswarmd.

        Args:
            bounty_guid (str): The bounty to assert on
            bid (int): The amount to bid
            mask (List[bool]): Which artifacts in the bounty to assert on
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        nonce, commitment = calculate_commitment(self.__client.account, bool_list_to_int(verdicts))

        path = '/bounties/{0}/assertions'.format(bounty_guid)
        assertion = {
            'bid': str(bid),
            'mask': mask,
            'commitment': commitment,
        }
        fee = self.parameters[chain]['assertion_fee']
        verifier = PostAssertionGroupVerifier(bounty_guid, bid, fee, mask, verdicts, nonce, self.__client.account)
        success, result = await self.__client.make_request_with_transactions('POST', path, chain, verifier,
                                                                             json=assertion,
                                                                             api_key=api_key)
        if not success or 'assertions' not in result:
            logger.error('Expected assertions, received', extra={'response': result})

        return nonce, result.get('assertions', [])

    async def post_reveal(self, bounty_guid, index, nonce, verdicts, metadata, chain, api_key=None):
        """Post an assertion reveal to polyswarmd.

        Args:
            bounty_guid (str): The bounty which we have asserted on
            index (int): The index of the assertion to reveal
            nonce (str): Secret nonce used to reveal assertion
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            metadata (str): Optional metadata
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        path = '/bounties/{0}/assertions/{1}/reveal'.format(bounty_guid, index)
        reveal = {
            'nonce': str(nonce),
            'verdicts': verdicts,
            'metadata': metadata,
        }
        verifier = RevealAssertionGroupVerifier(bounty_guid, index, nonce, verdicts, metadata, self.__client.account)
        success, result = await self.__client.make_request_with_transactions('POST', path, chain, verifier, json=reveal,
                                                                             api_key=api_key)
        if not success or 'reveals' not in result:
            logger.error('Expected reveal, received', extra={'response': result})

        return result.get('reveals', [])

    async def get_vote(self, bounty_guid, index, chain, api_key=None):
        """
        Get a vote from polyswamrd

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the vote from
            index (int): Index of the vote
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        """
        path = '/bounties/{0}/votes/{1}'.format(bounty_guid, index)
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        if not success:
            logger.error('Expected vote, received', extra={'response': result})
            return None

        return result

    async def post_vote(self, bounty_guid, votes, valid_bloom, chain, api_key=None):
        """Post a vote to polyswarmd.

        Args:
            bounty_guid (str): The bounty which we are voting on
            votes (List[bool]): Vote (malicious/benign) for each of the artifacts in the bounty
            valid_bloom (bool): Is the bloom filter reported by the bounty poster valid
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        path = '/bounties/{0}/vote'.format(bounty_guid)
        vote = {
            'votes': votes,
            'valid_bloom': valid_bloom,
        }
        verifier = PostVoteGroupVerifier(bounty_guid, votes, valid_bloom, self.__client.account)
        success, result = await self.__client.make_request_with_transactions('POST', path, chain, verifier, json=vote,
                                                                             api_key=api_key)
        if not success or 'votes' not in result:
            logger.error('Expected vote, received', extra={'response': result})

        return result.get('votes', [])

    async def settle_bounty(self, bounty_guid, chain, api_key=None):
        """Settle a bounty via polyswarmd

        Args:
            bounty_guid (str): The bounty which we are settling
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        path = '/bounties/{0}/settle'.format(bounty_guid)
        verifier = SettleBountyGroupVerifier(bounty_guid, self.__client.account)
        success, result = await self.__client.make_request_with_transactions('POST', path, chain, verifier,
                                                                             api_key=api_key)
        if not success or 'transfers' not in result:
            logger.warning('No transfer event, received (maybe expected)', extra={'response': result})

        return result.get('transfers', [])
