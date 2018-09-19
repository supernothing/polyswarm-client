import sqlite3
import hashlib
import os

from polyswarmclient.arbiter import Arbiter

ARTIFACT_DIRECTORY = os.getenv('ARTIFACT_DIRECTORY', 'docker/artifacts')


class VerbatimArbiter(Arbiter):
    """Arbiter which matches hashes to a database of known samples"""

    def __init__(self, polyswarmd_addr, keyfile, password, api_key=None, testing=0, insecure_transport=False, chains={'home'}):
        """Initialize a verbatim arbiter

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
        self.conn = sqlite3.connect(os.path.join(ARTIFACT_DIRECTORY, 'truth.db'))

    async def scan(self, guid, content, chain):
        """Match hash of an artifact with our database

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            content (bytes): Content of the artifact to be scan
            chain (str): Chain sample is being sent from
        Returns:
            (bool, bool, str): Tuple of bit, verdict, metadata

            bit (bool): Whether to include this artifact in the assertion or not
            verdict (bool): Whether this artifact is malicious or not
            metadata (str): Optional metadata about this artifact
        """
        h = hashlib.sha256(content).hexdigest()

        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM files WHERE name=?', (h,))
        row = cursor.fetchone()

        bit = row is not None
        verdict = row is not None and row[1] == 1

        return bit, verdict, ''
