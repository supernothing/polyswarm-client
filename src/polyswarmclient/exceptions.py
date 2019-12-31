
class PolyswarmClientException(Exception):
    """
    polyswarm-client related errors.
    """
    pass


class ApiKeyException(PolyswarmClientException):
    """
    Used an API key when not communicating over https.
    """
    pass


class ExpiredException(PolyswarmClientException):
    """
    Worker skipped scanning some artifact due to the bounty expiring before getting scanned.
    Seen when the worker was down for a period of time, or when there aren't enough workers to keep up with load.
    """
    pass


class InvalidBidError(PolyswarmClientException):
    """
    Fault in bid logic that resulted in a bid that is not between the min and max values provided by polyswarmd.
    """
    pass
