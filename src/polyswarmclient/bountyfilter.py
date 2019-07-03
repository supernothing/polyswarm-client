import click
import itertools
import logging

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
    if value is None:
        return value

    result = []
    for item in value:
        # Split only the first:
        kv = item.split(':', 1)
        if len(kv) != 2:
            raise click.BadParameter('Accept and exclude arguments must be formatted `key:value`')

        result.append((kv[0], kv[1]))
    return result


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
        if not self.accept and not self.exclude:
            return True

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
