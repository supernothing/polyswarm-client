import click
import logging

from polyswarmartifact.schema import Bounty

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
    """ Takes a pair of dictionaries: accept and include
        These dicts are used to filter metadata json blobs.
        Key value pairs in accept are required in metadata blobs
        k - v pairs in except are required to not be present in metadata
    """

    def __init__(self, accept, exclude):
        if accept is None:
            self.accept = []
        else:
            self.accept = accept

        if exclude is None:
            self.exclude = []
        else:
            self.exclude = exclude

    @staticmethod
    def pad_metadata(metadata, min_length):
        """ Pad out the metadata list with None values to match a given length

        Args:
            metadata (list[dict|None]): List of metadata dicts
            min_length (int): Min size for the metadata list after padding

        Returns:
            list of metadata dicts, or None values
        """
        result = metadata
        if not metadata or not Bounty.validate(metadata):
            result = [None] * min_length
        elif len(metadata) < min_length:
            result.extend([None] * (min_length - len(metadata)))

        logger.critical('Extended result %s', result)

        return result

    def is_allowed(self, metadata):
        """ Test if an artifact with given metadata the given metadata is allowed past the filter

        Args:
            metadata (dict): metadata dict to test

        Returns:
            (bool): True if meets the conditions and passes the filter
        """
        if not self.accept and not self.exclude:
            return True

        accepted = any([v == metadata.get(k, None) for k, v in self.accept])
        if self.accept and not accepted:
            logger.info('Metadata is not supported. Skipping artifact', extra={"extra": metadata})
            return False

        for k, v in self.exclude:
            metadata_value = metadata.get(k, None)
            if v == metadata_value:
                logger.info('%s %s is excluded. Skipping artifact', k, metadata_value)
                return False

        return True
