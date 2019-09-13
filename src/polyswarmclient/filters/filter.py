import enum
import logging
import re

from polyswarmartifact.schema import Bounty


logger = logging.getLogger(__name__)


def parse_filters(ctx, param, value):
    """ Split some filters into a dict separated by type

        Args:
            ctx:
            param:
            value: list of 4 string tuples

        Returns:
            dict: Dict where each key points to a list of Filters
        """
    if not value:
        return {}

    response = {}

    for filter_type, key, comparison_string, target_value in value:
        # Click only accepts the string values for each member in FilterComparison
        comparison = FilterComparison.from_string(comparison_string)
        # Make sure the filter type exists in the response dict
        if not response.get(filter_type, None):
            response[filter_type] = []

        response[filter_type].append(Filter(key, comparison, target_value))

    return response


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
    def __init__(self, key, comparison, target_value):
        """ Create a new Filter

        Args:
            key (str): Key name for the metadata field being filtered
            comparison (FilterComparison): Type of comparison
            target_value (str): Str representation of the target value
        """
        self.key = key
        self.comparison = comparison
        self.target_value = target_value

    def __eq__(self, other):
        return isinstance(other, Filter) \
               and other.key == self.key \
               and other.comparison == self.comparison \
               and other.target_value == self.target_value

    def __repr__(self):
        return '<Filter key={0} comparison={1} target_value={2}>'.format(self.key,
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

    def filter(self, metadata):
        """ Take some metadata, and matches the given key against the target_value and comparison operator for this filter

        Args:
            metadata (dict): Dict of k-v metadata values

        Returns: (bool) True if it matches the filter
        """
        if metadata is None or not isinstance(metadata, dict):
            return False

        value = metadata.get(self.key, None)
        if value is None:
            return False

        if self.comparison in [FilterComparison.GT, FilterComparison.GTE, FilterComparison.LT, FilterComparison.LTE]:
            return self.number_check(value)

        return self.string_check(value)


class MetadataFilter:
    """ Takes two objects list[Filter], accept and reject
        These dicts are used to filter metadata json blobs.
        Each filter runs against given metadata, and is used to determine if this participant will respond to a bounty
    """

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

        logger.debug('Padded result %s:', result)

        return result
