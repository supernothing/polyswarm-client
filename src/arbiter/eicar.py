import base64
import logging

from polyswarmartifact import ArtifactType

from polyswarmclient.abstractarbiter import AbstractArbiter
from polyswarmclient.abstractscanner import ScanResult

logger = logging.getLogger(__name__)  # Initialize logger
EICAR = base64.b64decode(
    b'WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo=')


class Arbiter(AbstractArbiter):
    """Arbiter which matches hashes to a database of known samples"""

    def __init__(self, client, testing=0, scanner=None, chains=None, artifact_types=None):
        """Initialize a verbatim arbiter

        Args:
            client (polyswwarmclient.Client): Client to use
            testing (int): How many test bounties to respond to
            chains (set[str]): Chain(s) to operate on
            artifact_types (list(ArtifactType)): List of artifact types you support
        """
        if artifact_types is None:
            artifact_types = [ArtifactType.FILE]
        super().__init__(client, testing, scanner, chains, artifact_types)

    async def scan(self, guid, artifact_type, content, metadata, chain):
        """Scan an artifact

        Args:
            guid (str): GUID of the bounty under analysis, use to track artifacts in the same bounty
            artifact_type (ArtifactType): Artifact type for the bounty being scanned
            content (bytes): Content of the artifact to be scan
            metadata (dict) Dict of metadata for the artifact
            chain (str): Chain we are operating on
        Returns:
            ScanResult: Result of this scan
        """
        return ScanResult(bit=True, verdict=(content == EICAR))

