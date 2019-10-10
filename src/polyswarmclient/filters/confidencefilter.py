import json
import logging

from polyswarmclient.filters.filter import Filter, MetadataFilter

logger = logging.getLogger(__name__)


class ConfidenceModifier(MetadataFilter):
    def __init__(self, favor, penalize):
        """ Create a new BountyFilter object with an array of Filters and RejectFilters
        Args:
            favor (None|list[Filter]): List of Filters for accepted bounties
            penalize (None|list[Filter]): List of Filters for rejected bounties
        """
        if favor is None:
            self.favor = []
        else:
            self.favor = favor

        if penalize is None:
            self.penalize = []
        else:
            self.penalize = penalize

    def modify(self, metadata, confidence):
        """Check metadata against the penalty and favor filters.
        Matching both bonus and penalty results offset

        Args:
            metadata (any): metadata dict to test
            confidence (float): confidence as returned by the Av engine

        Returns:
            (float): confidence that is either more, same or less after comparing against bonus/penalty Filters
        """
        if not self.favor and not self.penalize:
            return confidence

        favored = any([f.filter(metadata) for f in self.favor])

        penalized = any([f.filter(metadata) for f in self.penalize])

        if favored and not penalized:
            logger.debug('Increasing confidence for favored value %s', json.dumps(metadata),
                         extra={'extra': self.favor})
            return confidence * 1.2
        elif penalized and not favored:
            logger.debug('Decreasing confidence for penalized value %s', json.dumps(metadata),
                         extra={'extra': self.penalize})
            return confidence * .8
        else:
            return confidence
