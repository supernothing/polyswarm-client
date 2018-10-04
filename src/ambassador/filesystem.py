import logging
import random
import os

from polyswarmclient.ambassador import Ambassador

ARTIFACT_DIRECTORY = os.getenv('ARTIFACT_DIRECTORY', 'docker/artifacts')
ARTIFACT_BLACKLIST = os.getenv('ARTIFACT_BLACKLIST', 'truth.db').split(',')

class FilesystemAmbassador(Ambassador):
    """Ambassador which submits artifacts from a directory"""

    def __init__(self, client, testing=0, chains={'home'}):
        """Initialize a filesystem ambassador

        Args:
            client (`Client`): Client to use
            testing (int): How many test bounties to respond to
            chains (set[str]): Chain(s) to operate on
        """
        super().__init__(client, testing, chains)

        self.artifacts = []
        for root, dirs, files in os.walk(ARTIFACT_DIRECTORY):
            for f in files:
                self.artifacts.append(os.path.join(root, f))

    async def next_bounty(self, chain):
        """Submit either the EICAR test string or a benign sample
        
        Args:
            chain (str): Chain sample is being requested from
        Returns:
            (int, str, int): Tuple of amount, ipfs_uri, duration, None to terminate submission

        Note:
            | The meaning of the return types are as follows:
            |   - **amount** (*int*): Amount to place this bounty for
            |   - **ipfs_uri** (*str*): IPFS URI of the artifact to post
            |   - **duration** (*int*): Duration of the bounty in blocks
        """
        amount = self.client.bounties.parameters[chain]['bounty_amount_minimum']
        filename = random.choice(self.artifacts)
        duration = 20

        logging.info('Submitting file %s', filename)
        ipfs_uri = await self.client.post_artifacts([(filename, None)])
        if not ipfs_uri:
            logging.error('Could not submit artifact to IPFS')
            return None

        return amount, ipfs_uri, duration
