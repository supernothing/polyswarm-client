import base64
import logging
import random
import os

from concurrent.futures import CancelledError
from polyswarmclient.abstractambassador import AbstractAmbassador

logger = logging.getLogger(__name__)

EICAR = base64.b64decode(
    b'WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=')
NOT_EICAR = 'this is not malicious'
ARTIFACTS = [('eicar', EICAR), ('not_eicar', NOT_EICAR)]
BOUNTY_TEST_DURATION_BLOCKS = int(os.getenv('BOUNTY_TEST_DURATION_BLOCKS', 5))


class Ambassador(AbstractAmbassador):
    """Ambassador which submits the EICAR test file"""

    async def generate_bounties(self, chain):
        """Submit either the EICAR test string or a benign sample

        Args:
            chain (str): Chain sample is being requested from
        """
        amount = await self.client.bounties.parameters[chain].get('bounty_amount_minimum')

        while True:
            try:
                filename, content = random.choice(ARTIFACTS)

                logger.info('Submitting %s', filename)
                ipfs_uri = await self.client.post_artifacts([(filename, content)])
                if not ipfs_uri:
                    logger.error('Error uploading artifact to IPFS, continuing')
                    continue

                await self.push_bounty(amount, ipfs_uri, BOUNTY_TEST_DURATION_BLOCKS, chain)
            except CancelledError:
                logger.warning('Cancel requested')
                break
            except Exception:
                logger.exception('Exception in bounty generation task, continuing')
                continue
