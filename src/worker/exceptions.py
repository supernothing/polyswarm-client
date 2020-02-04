from polyswarmclient.exceptions import PolyswarmClientException


class ExpiredException(PolyswarmClientException):
    """
    Worker skipped scanning some artifact due to the bounty expiring before getting scanned.
    Seen when the worker was down for a period of time, or when there aren't enough workers to keep up with load.
    """
    pass


class EmptyJobsQueueException(PolyswarmClientException):
    """
    Worker Queue is empty
    """
    pass
