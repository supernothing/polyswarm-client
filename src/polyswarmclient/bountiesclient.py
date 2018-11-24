import logging

from polyswarmclient import bloom

logger = logging.getLogger(__name__)  # Initialize logger


class BountiesClient(object):
    def __init__(self, client):
        self.__client = client
        self.parameters = {}

    async def get_parameters(self, chain):
        """Get bounty parameters from polyswarmd.

        Args:
            chain (str): Which chain to operate on.
        Note:
            This function doesn't return anything. It instead stores the bounty parameters
            as parsed JSON in self.parameters[chain].
        """
        success, result = await self.__client.make_request('GET', '/bounties/parameters', chain)
        if not success:
            raise Exception('Error retrieving bounty parameters')
        self.parameters[chain] = result

    async def calculate_bloom(self, ipfs_uri):
        """Calculate bloom filter for a set of artifacts.

        Args:
            ipfs_uri (str): IPFS URI for the artifact set
        Returns:
            Bloom filter value for the artifact set
        """
        artifacts = await self.__client.list_artifacts(ipfs_uri)
        bf = bloom.BloomFilter()
        for _, h in artifacts:
            bf.add(h.encode('utf-8'))

        return int(bf)

    async def get_bloom(self, bounty_guid, chain):
        """
        Get a vote from polyswamrd

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the vote from
            chain (str): Which chain to operate on
        """
        path = '/bounties/{0}/bloom'.format(bounty_guid)
        success, result = await self.__client.make_request('GET', path, chain)
        if not success:
            logger.error('Expected bloom, received', extra={'response': result})
            return None
        return result.get('bloom')

    async def get_bounty(self, guid, chain):
        """Get a bounty from polyswarmd.

        Args:
            guid (str): GUID of the bounty to retrieve
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing bounty details
        """
        path = '/bounties/{0}'.format(guid)
        success, result = await self.__client.make_request('GET', path, chain)
        if not success:
            logger.error('Expected bounty, received', extra={'response': result})
            return None

        return result

    async def post_bounty(self, amount, artifact_uri, duration, chain):
        """Post a bounty to polyswarmd.

        Args:
            amount (int): The amount to put up as a bounty
            artifact_uri (str): URI of artifacts
            duration (int): Number of blocks to accept new assertions
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        bounty = {
            'amount': str(amount),
            'uri': artifact_uri,
            'duration': duration,
        }
        success, result = await self.__client.make_request_with_transactions('POST', '/bounties', chain, json=bounty)
        if not success or 'bounties' not in result:
            logger.error('Expected bounty, received', extra={'response': result})

        return result.get('bounties', [])

    async def get_assertion(self, bounty_guid, index, chain):
        """Get an assertion from polyswarmd.

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the assertion from
            index (int): Index of the assertion
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing assertion details
        """
        path = '/bounties/{0}/assertions/{1}'.format(bounty_guid, index)
        success, result = await self.__client.make_request('GET', path, chain)
        if not success:
            logger.error('Expected assertion, received', extra={'response': result})
            return None

        return result

    async def post_assertion(self, bounty_guid, bid, mask, verdicts, chain):
        """Post an assertion to polyswarmd.

        Args:
            bounty_guid (str): The bounty to assert on
            bid (int): The amount to bid
            mask (List[bool]): Which artifacts in the bounty to assert on
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        path = '/bounties/{0}/assertions'.format(bounty_guid)
        assertion = {
            'bid': str(bid),
            'mask': mask,
            'verdicts': verdicts,
        }
        success, result = await self.__client.make_request_with_transactions('POST', path, chain, json=assertion)
        if not success or 'nonce' not in result or 'assertions' not in result:
            logger.error('Expected nonce and assertions, received', extra={'response': result})

        return result.get('nonce', -1), result.get('assertions', [])

    async def post_reveal(self, bounty_guid, index, nonce, verdicts, metadata, chain):
        """Post an assertion reveal to polyswarmd.

        Args:
            bounty_guid (str): The bounty which we have asserted on
            index (int): The index of the assertion to reveal
            nonce (str): Secret nonce used to reveal assertion
            verdicts (List[bool]): Verdict (malicious/benign) for each of the artifacts in the bounty
            metadata (str): Optional metadata
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        path = '/bounties/{0}/assertions/{1}/reveal'.format(bounty_guid, index)
        reveal = {
            'nonce': nonce,
            'verdicts': verdicts,
            'metadata': metadata,
        }
        success, result = await self.__client.make_request_with_transactions('POST', path, chain, json=reveal)
        if not success or 'reveals' not in result:
            logger.error('Expected reveal, received', extra={'response': result})

        return result.get('reveals', [])

    async def get_vote(self, bounty_guid, index, chain):
        """
        Get a vote from polyswamrd

        Args:
            bounty_guid (str): GUID of the bounty to retrieve the vote from
            index (int): Index of the vote
            chain (str): Which chain to operate on
        """
        path = '/bounties/{0}/votes/{1}'.format(bounty_guid, index)
        success, result = await self.__client.make_request('GET', path, chain)
        if not success:
            logger.error('Expected vote, received', extra={'response': result})
            return None

        return result

    async def post_vote(self, bounty_guid, votes, valid_bloom, chain):
        """Post a vote to polyswarmd.

        Args:
            bounty_guid (str): The bounty which we are voting on
            votes (List[bool]): Vote (malicious/benign) for each of the artifacts in the bounty
            valid_bloom (bool): Is the bloom filter reported by the bounty poster valid
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        path = '/bounties/{0}/vote'.format(bounty_guid)
        vote = {
            'votes': votes,
            'valid_bloom': valid_bloom,
        }
        success, result = await self.__client.make_request_with_transactions('POST', path, chain, json=vote)
        if not success or 'votes' not in result:
            logger.error('Expected vote, received', extra={'response': result})

        return result.get('votes', [])

    async def settle_bounty(self, bounty_guid, chain):
        """Settle a bounty via polyswarmd

        Args:
            bounty_guid (str): The bounty which we are settling
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        path = '/bounties/{0}/settle'.format(bounty_guid)
        success, result = await self.__client.make_request_with_transactions('POST', path, chain)
        if not success or 'transfers' not in result:
            logger.warning('No transfer event, received (maybe expected)', extra={'response': result})

        return result.get('transfers', [])
