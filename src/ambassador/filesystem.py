import logging
import random
import os

from polyswarmclient.ambassador import Ambassador

ARTIFACT_DIRECTORY = os.getenv('ARTIFACT_DIRECTORY', 'docker/artifacts')

class FilesystemAmbassador(Ambassador):
    """Ambassador which submits artifacts from a directory"""

    def __init__(self, polyswarmd_addr, keyfile, password, api_key=None, testing=0, insecure_transport=False, chains={'home'}):
        """Initialize a filesystem ambassador

        Args:
            polyswarmd_addr (str): Address of polyswarmd
            keyfile (str): Path to private key file to use to sign transactions
            password (str): Password to decrypt the encrypted private key
            api_key (str): API key to use with polyswarmd
            testing (int): How many test bounties to respond to
            insecure_transport (bool): Connect to polyswarmd over an insecure transport
            chains (set[str]): Chain(s) to operate on
        """
        super().__init__(polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, chains)
        
        benign_path = os.path.join(ARTIFACT_DIRECTORY, 'benign')
        benign_artifacts = [os.path.join(benign_path, a) for a in os.listdir(benign_path)]
        malicious_path = os.path.join(ARTIFACT_DIRECTORY, 'malicious')
        malicious_artifacts = [os.path.join(malicious_path, a) for a in os.listdir(malicious_path)]

        self.artifacts = benign_artifacts + malicious_artifacts

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
        filename = random.choice(self.artifacts)
        duration = 20

        logging.info('Submitting file %s', filename)
        ipfs_uri = await self.client.post_artifacts([(filename, None)])
        if not ipfs_uri:
            logging.error('Could not submit artifact to IPFS')
            return None

        return amount, ipfs_uri, duration
