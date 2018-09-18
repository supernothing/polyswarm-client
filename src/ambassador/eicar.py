import base64
import logging
import random

from polyswarmclient.ambassador import Ambassador

EICAR = base64.b64decode(b'WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=')
NOT_EICAR = 'this is not malicious'
ARTIFACTS = [('eicar', EICAR), ('not_eicar', NOT_EICAR)]

class EicarAmbassador(Ambassador):
    """Ambassador which submits the EICAR test file"""

    async def next_bounty(self, chain):
        """Submit either the EICAR test string or a benign sample

        Args:
            chain (str): Chain sample is being requested from
        Returns:
            (int, str, int): Tuple of amount, ipfs_uri, duration, None to terminate submission

            amount (int): Amount to place this bounty for
            ipfs_uri (str): IPFS URI of the artifact to post
            duration (int): Duration of the bounty in blocks
        """
        amount = self.client.bounties.parameters[chain]['bounty_amount_minimum']
        filename, content = random.choice(ARTIFACTS)
        duration = 20

        logging.info('Submitting %s', filename)
        ipfs_uri = await self.client.post_artifacts([(filename, content)])
        if not ipfs_uri:
            logging.error('Could not submit artifact to IPFS')
            return None

        return amount, ipfs_uri, duration
