import enum
import re
import click
import logging

from jq import jq

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
    if not value:
        return value

    result = []
    for item in value:
        # Split only the first:
        kv = item.split(':', 1)
        if len(kv) != 2:
            raise click.BadParameter('Accept and exclude arguments must be formatted `key:value`')

        # Set filter to match jq format
        result.append(Filter(".{0}".format(kv[0]), FilterComparison.EQ, kv[1]))
    return result


def parse_filters(ctx, param, value):
    """ Split some accept or exlcude arg from `key:value` to a tuple

        Args:
            ctx:
            param:
            value: list of 4 string tuples

        Returns:
            tuple[list[Filter], list[Filter]]: tuple of lists where 0 is accept filters, 1 is reject filters
        """
    if not value:
        return [], []

    accept = []
    reject = []
    for filter_type, key, comparison_string, target_value in value:
        # Click only accepts the string values for each member in FilterComparison
        comparison = FilterComparison.from_string(comparison_string)
        if filter_type == 'accept':
            accept.append(Filter(key, comparison, target_value))
        else:
            reject.append(Filter(key, comparison, target_value))

    return accept, reject


class FilterComparison(enum.Enum):
    """ Enum of supported metadata comparisons"""
    LT = '<'
    LTE = '<='
    EQ = '=='
    GTE = '>='
    GT = '>'
    CONTAINS = 'contains'
    STARTS_WITH = 'startswith'
    ENDS_WITH = 'endswith'
    REGEX = 'regex'

    def __repr__(self):
        return '<FilterComparison name={0} value={1}>'.format(self.name, self.value)

    @staticmethod
    def from_string(value):
        for name, member in FilterComparison.__members__.items():
            if member.value == value:
                return FilterComparison[name]

        return None


class Filter:
    """ Filter some metadata value

    """
    def __init__(self, query, comparison, target_value):
        """ Create a new Filter

        Args:
            query (str): JQ style query to get the intended kv pair
            comparison (FilterComparison): Type of comparison
            target_value (str): Str representation of the target value
        """
        self.jq = jq(query)
        self.query = query
        self.comparison = comparison
        self.target_value = target_value

    def __eq__(self, other):
        return isinstance(other, Filter) \
               and other.query == self.query \
               and other.comparison == self.comparison \
               and other.target_value == self.target_value

    def __repr__(self):
        return '<Filter query={0} comparison={1} target_value={2}>'.format(self.query,
                                                                           self.comparison,
                                                                           self.target_value)

    def number_check(self, value):
        """ Check a value as a number with GT, GTE, LT, or LTE comparisons

        Args:
            value (str|int|float|bytes): Value to compare against

        Returns: (bool) returns True if comparison matches

        """
        try:
            match = False
            if self.comparison == FilterComparison.GT:
                match = float(value) > float(self.target_value)
            elif self.comparison == FilterComparison.GTE:
                match = float(value) >= float(self.target_value)
            elif self.comparison == FilterComparison.LT:
                match = float(value) < float(self.target_value)
            elif self.comparison == FilterComparison.LTE:
                match = float(value) <= float(self.target_value)
            return match
        except ValueError:
            logger.warning('Using integer specific %s comparison, but have non-integer value %s or target %s',
                           self.comparison, value, self.target_value)
            return False

    def string_check(self, value):
        """ Check a value as a string with EQ, CONTAINS, STARTS_WITH, ENDS_WITH, and REGEX comparisons

        Args:
            value (str|int|float|bytes): Value to compare against

        Returns: (bool) returns True if comparison matches

        """
        match = False
        if self.comparison == FilterComparison.EQ:
            match = str(value) == self.target_value
        elif self.comparison == FilterComparison.CONTAINS:
            match = self.target_value in str(value)
        elif self.comparison == FilterComparison.STARTS_WITH:
            match = str(value).startswith(self.target_value)
        elif self.comparison == FilterComparison.ENDS_WITH:
            match = str(value).endswith(self.target_value)
        elif self.comparison == FilterComparison.REGEX:
            match = bool(re.search(self.target_value, str(value)))

        return match

    def filter(self, value):
        """ Take a value, and match it against the target_value and comparison operator for this filter

        Args:
            value (any): Some value to compare against

        Returns: (bool) True if it matches the filter

        """
        try:
            transformed = self.jq.transform(value)
        except ValueError:
            logger.error('Cannot parse value %s with query %s', value, self.query)
            return False

        if transformed is None:
            return False

        if self.comparison in [FilterComparison.GT, FilterComparison.GTE, FilterComparison.LT, FilterComparison.LTE]:
            return self.number_check(transformed)

        return self.string_check(transformed)


class BountyFilter:
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
            result = [{}] * min_length
        elif len(metadata) < min_length:
            result.extend([{}] * (min_length - len(metadata)))

        logger.info('Padded result %s:', result)

        return result

    def is_allowed(self, metadata):
        """Check metadata against the accept and exclude filters, returning True if it passes all checks

        Args:
            metadata (dict): metadata dict to test

        Returns:
            (bool): True if meets the conditions and passes the filter
        """
        if not self.accept and not self.reject:
            return True

        accepted = any((f.filter(metadata) for f in self.accept))

        if self.accept and not accepted:
            logger.info('Metadata not accepted. Skipping artifact', extra={"extra": {"metadata": metadata,
                                                                                     "accept": self.accept}})
            return False

        rejected = any((f.filter(metadata) for f in self.reject))
        if self.reject and rejected:
            logger.info('Metadata rejected. Skipping artifact', extra={"extra": {"metadata": metadata,
                                                                                 "reject": self.reject}})
            return False

        return True
