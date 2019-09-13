import click
import logging

from polyswarmclient.filters.filter import MetadataFilter, Filter, FilterComparison

logger = logging.getLogger(__name__)


def split_filter(ctx, param, value):
    """ Split some accept or exlcude arg from `key:value` to a tuple

    Args:
        ctx:
        param:
        value: list of exclude or accept values

    Returns:
        list[tuple] list of exclude|accept values as tuple key, value
    """
    if not value:
        return value

    result = []
    for item in value:
        # Split only the first:
        kv = item.split(':', 1)
        if len(kv) != 2:
            raise click.BadParameter('Accept and exclude arguments must be formatted `key:value`')

        result.append(Filter(kv[0], FilterComparison.EQ, kv[1]))
    return result


class BountyFilter(MetadataFilter):
    """ Takes two objects list[Filter], accept and reject
        These dicts are used to filter metadata json blobs.
        Each filter runs against given metadata, and is used to determine if this participant will respond to a bounty
    """
    def __init__(self, accept, reject):
        """ Create a new BountyFilter object with an array of Filters and RejectFilters
        Args:
            accept (None|list[Filter]): List of Filters for accepted bounties
            reject (None|list[Filter]): List of Filters for rejected bounties
        """
        if accept is None:
            self.accept = []
        else:
            self.accept = accept

        if reject is None:
            self.reject = []
        else:
            self.reject = reject

    def is_allowed(self, metadata):
        """Check metadata against the accept and exclude filters, returning True if it passes all checks

        Args:
            metadata (dict): metadata dict to test

        Returns:
            (bool): True if meets the conditions and passes the filter
        """
        if not self.accept and not self.reject:
            return True

        accepted = any([f.filter(metadata) for f in self.accept])

        if self.accept and not accepted:
            logger.debug('Metadata not accepted. Skipping artifact', extra={'extra': {'metadata': metadata,
                                                                            'accept': self.accept}})
            return False

        rejected = any([f.filter(metadata) for f in self.reject])
        if self.reject and rejected:
            logger.debug('Metadata rejected. Skipping artifact', extra={'extra': {'metadata': metadata,
                                                                        'reject': self.reject}})
            return False

        return True
