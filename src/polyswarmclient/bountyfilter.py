import itertools
import logging

logger = logging.getLogger(__name__)


class BountyFilter:
    """ Takes a pair of dictionarys: accept and include
        These dicts are used to filter metadata json blobs.
        Key value pairs in accept are required in metadata blobs
        k - v pairs in except are required to not be present in metadata
    """

    def __init__(self, accept, exclude):
        self.accept = accept
        self.exclude = exclude

    def is_valid(self, metadata):
        if self.accept or self.exclude:
            for accept_pair, exclude_pair in itertools.zip_longest(self.accept, self.exclude):
                if accept_pair:
                    k, v = accept_pair
                    metadata_value = metadata.get(k, None)
                    if v != metadata_value:
                        logger.info('%s %s is not supported. Skipping artifact', k, metadata_value)
                        return False

                if exclude_pair:
                    k, v = exclude_pair
                    metadata_value = metadata.get(k, None)
                    if v == metadata_value:
                        logger.info('%s %s is excluded. Skipping artifact', k, metadata_value)
                        return False

        return True

