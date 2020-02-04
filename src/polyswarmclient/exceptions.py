
class PolyswarmClientException(Exception):
    """
    polyswarm-client related errors
    """
    pass


class ApiKeyException(PolyswarmClientException):
    """
    Used an API key when not communicating over https.
    """
    pass


class InvalidBidError(PolyswarmClientException):
    """
    Fault in bid logic that resulted in a bid that is not between the min and max values provided by polyswarmd
    """
    pass


class LowBalanceError(PolyswarmClientException):
    """
    Not enough NCT to complete the requested action
    """
    pass
