import base64
import sqlite3
import hashlib
import logging
import os

from polyswarmclient.abstractarbiter import AbstractArbiter
from polyswarmclient.abstractscanner import ScanResult
from polyswarmclient.corpus import DownloadToFileSystemCorpus

logger = logging.getLogger(__name__)  # Initialize logger
ARTIFACT_DIRECTORY = os.getenv('ARTIFACT_DIRECTORY', 'docker/artifacts')
EICAR = base64.b64decode(
    b'WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=')


class Arbiter(AbstractArbiter):
    """Arbiter which matches hashes to a database of known samples"""

    def __init__(self, client, testing=0, scanner=None, chains=None):
        """Initialize a verbatim arbiter

        Args:
            client (polyswwarmclient.Client): Client to use
            testing (int): How many test bounties to respond to
            chains (set[str]): Chain(s) to operate on
        """
        super().__init__(client, testing, None, chains)
        db_pth = os.path.join(ARTIFACT_DIRECTORY, 'truth.db')

        if os.getenv("MALICIOUS_BOOTSTRAP_URL"):

            d = DownloadToFileSystemCorpus(base_dir=ARTIFACT_DIRECTORY)
            d.download_truth()
            self.conn = sqlite3.connect(d.truth_db_pth)
        else:
            self.conn = sqlite3.connect(db_pth)

    async def scan(self, guid, content, chain):
        """Match hash of an artifact with our database

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            content (bytes): Content of the artifact to be scan
            chain (str): Chain sample is being sent from
        Returns:
            ScanResult: Result of this scan
        """
        h = hashlib.sha256(content).hexdigest()

        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM files WHERE name=?', (h,))
        row = cursor.fetchone()

        bit = row is not None
        vote = row is not None and row[1] == 1
        vote = vote or EICAR in content

        return ScanResult(bit=bit, verdict=vote)
