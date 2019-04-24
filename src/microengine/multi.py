import asyncio
import logging

from polyswarmclient.abstractmicroengine import AbstractMicroengine
from polyswarmclient.abstractscanner import AbstractScanner, ScanResult
from microengine.clamav import Scanner as ClamavScanner
from microengine.yara import Scanner as YaraScanner

logger = logging.getLogger(__name__)
BACKENDS = [ClamavScanner, YaraScanner]


class Scanner(AbstractScanner):

    def __init__(self):
        super(Scanner, self).__init__()
        self.backends = [cls() for cls in BACKENDS]

    async def scan(self, guid, content, chain):
        """Scan an artifact

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            content (bytes): Content of the artifact to be scan
            chain (str): Chain we are operating on
        Returns:
            ScanResult: Result of this scan
        """
        results = await asyncio.gather(*[backend.scan(guid, content, chain) for backend in self.backends])

        # Unpack the results
        bits = [r.bit for r in results]
        verdicts = [r.verdict for r in results]
        confidences = [r.confidence for r in results]
        metadatas = [r.metadata for r in results]

        asserted_confidences = [c for b, c in zip(bits, confidences) if b]
        avg_confidence = sum(asserted_confidences) / len(asserted_confidences)

        return ScanResult(bit=any(bits), verdict=any(verdicts), confidence=avg_confidence, metadata=';'.join(metadatas))


class Microengine(AbstractMicroengine):
    """Microengine which aggregates multiple sub-microengines"""

    def __init__(self, client, testing=0, scanner=None, chains=None):
        """Initialize a multi-backend microengine

        Args:
            client (polyswarmclient.Client): Client to use
            testing (int): How many test bounties to respond to
            chains (set[str]): Chain(s) to operate on
        """
        scanner = Scanner()
        super().__init__(client, testing, scanner, chains)
