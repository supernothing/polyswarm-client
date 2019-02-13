import clamd
import logging
import os
from io import BytesIO

from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult

logger = logging.getLogger(__name__)

CLAMD_HOST = os.getenv('CLAMD_HOST', 'localhost')
CLAMD_PORT = int(os.getenv('CLAMD_PORT', '3310'))
CLAMD_TIMEOUT = 30.0


class Scanner(AbstractScanner):
    def __init__(self):
        self.clamd = clamd.ClamdAsyncNetworkSocket(CLAMD_HOST, CLAMD_PORT, CLAMD_TIMEOUT)

    async def scan(self, guid, content, chain):
        """Scan an artifact with ClamAV

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            content (bytes): Content of the artifact to be scan
            chain (str): Chain we are operating on
        Returns:
            ScanResult: Result of this scan
        """
        result = await self.clamd.instream(BytesIO(content))
        stream_result = result.get('stream', [])
        if len(stream_result) >= 2 and stream_result[0] == 'FOUND':
            return ScanResult(bit=True, verdict=True, confidence=1.0, metadata=stream_result[1])

        return ScanResult(bit=True, verdict=False)


class Microengine(AbstractMicroengine):
    """
    Microengine which scans samples through clamd.

    Args:
        client (`Client`): Client to use
        testing (int): How many test bounties to respond to
        chains (set[str]): Chain(s) to operate on
    """

    def __init__(self, client, testing=0, scanner=None, chains=None):
        """Initialize a ClamAV microengine"""
        scanner = Scanner()
        super().__init__(client, testing, scanner, chains)
