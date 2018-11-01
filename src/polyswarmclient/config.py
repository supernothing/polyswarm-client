import logging

from polyswarmclient.log_formatter import JSONFormatter
from pythonjsonlogger import jsonlogger


class ExtraTextFormatter(logging.Formatter):
    """
    Custom formatter that adds extra fields to the message string
    """
    def format(self, record):
        """
        Takes a LogRecord and sets record.message = record.msg % record.args
        This one does some extra work.
        It searches the record dict for some extra keys we use in the client. (specified as extra= in the logger statement)
        If it finds one, it grabs the dict and adds an extra %s arg to record.msg, and the dict value to the record.args tuple.
        """
        # search for extra keys in the dict.
        extra = record.__dict__.get('extra')
        if extra is not None:
            # Add the extra value to the msg format string and the dict to the tuple
            record.msg += ': %s'
            # add extra dict as a tuple
            record.args = record.args + (extra,)

        return super().format(record)

def init_logging(log_format, loglevel=logging.INFO):
    """
    Logic to support JSON logging.
    """
    logger = logging.getLogger()  # Root logger
    if log_format and log_format in ['json', 'datadog']:
        logHandler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter()
        formatter = JSONFormatter('(level) (name) (timestamp) (message)')
        logHandler.setFormatter(formatter)
        logger.addHandler(logHandler)
        logger.setLevel(loglevel)
        logger.info("Logging in JSON format.")
    else:
        logHandler = logging.StreamHandler()
        logHandler.setFormatter(ExtraTextFormatter(fmt='%(levelname)s:%(name)s:%(asctime)s %(message)s'))
        logger.addHandler(logHandler)
        logger.setLevel(loglevel)
        logger.info("Logging in text format.")
