import logging

from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult

logger = logging.getLogger(__name__)  # Initialize logger


class Scanner(AbstractScanner):

    def __init__(self):
        super(Scanner, self).__init__()

    async def scan(self, guid, content, chain):
        """Scan an artifact

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            content (bytes): Content of the artifact to be scan
            chain (str): Chain we are operating on
        Returns:
            ScanResult: Result of this scan
        """
        return ScanResult()


class Microengine(AbstractMicroengine):
    """
    Scratch microengine is the same as the default behavior.

    Args:
        client (`Client`): Client to use
        testing (int): How many test bounties to respond to
        chains (set[str]): Chain(s) to operate on
    """
    def __init__(self, client, testing=0, scanner=None, chains=None):
        """Initialize Scanner"""
        scanner = Scanner()
        super().__init__(client, testing, scanner, chains)
