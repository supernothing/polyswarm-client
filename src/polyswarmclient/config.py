import click
import logging

from polyswarmclient.log_formatter import JSONFormatter, ExtraTextFormatter
from pythonjsonlogger import jsonlogger

logger = logging.getLogger(__name__)


def validate_apikey(ctx, param, value):
    """Validates the API key passed in through click parameters"""
    try:
        # If we recieved the parameter's default value, then don't bother
        # checking.
        if value == param.get_default(ctx):
            return value
        # int(x, 16) doesn't check newlines, etc. This ensures we've got a clean API key
        if len(value) != 32:
            raise click.BadParameter('API key must be 32 characters')
        if format(int(value, 16), 'x') != value:
            raise click.BadParameter("API key is an invalid 16-byte hex value.")
        return value
    except ValueError:
        raise click.BadParameter("API key must only contain valid hexadecimal values")
    except TypeError:
        # I don't believe this can ever be triggered as a click option, but I'm
        # keeping it around for completeness.
        raise click.BadParameter("API key must be a string")

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
