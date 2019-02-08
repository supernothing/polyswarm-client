import logging

from polyswarmclient.log_formatter import JSONFormatter, ExtraTextFormatter
from pythonjsonlogger import jsonlogger

logger = logging.getLogger(__name__)


def init_logging(log_format, loglevel=logging.WARNING):
    """
    Logic to support JSON logging.
    """
    # Change settings on polyswarm-client logger
    logger_config = LoggerConfig(log_format, loglevel)
    logger_config.configure('polyswarmclient')


class LoggerConfig:
    def __init__(self, log_format, log_level=logging.WARNING):
        self.log_format = log_format
        self.log_level = log_level

    def configure(self, name):
        configured = logging.getLogger(name)
        if self.log_format and self.log_format in ['json', 'datadog']:
            log_handler = logging.StreamHandler()
            formatter = JSONFormatter('(level) (name) (timestamp) (message)')
            log_handler.setFormatter(formatter)
            configured.addHandler(log_handler)
            configured.setLevel(self.log_level)
            configured.info("Logging in JSON format.")
        else:
            log_handler = logging.StreamHandler()
            log_handler.setFormatter(ExtraTextFormatter(fmt='%(levelname)s:%(name)s:%(asctime)s %(message)s'))
            configured.addHandler(log_handler)
            configured.setLevel(self.log_level)
            configured.info("Logging in text format.")
