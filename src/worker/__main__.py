import click
import importlib.util
import logging
import sys

from worker import Worker
from polyswarmclient.config import init_logging, validate_apikey

logger = logging.getLogger(__name__)  # Initialize logger


def choose_backend(backend):
    """Resolves scanner name string to implementation

    Args:
        backend (str): Name of the backend to load, either one of the predefined implementations or the name of a module
        to load

        (module:ClassName syntax or default of module:Scanner)
    Returns:
        (Class): Scanner class of the selected implementation
    Raises:
        (Exception): If backend is not found
    """
    backend_list = backend.split(":")
    module_name_string = backend_list[0]

    # determine if this string is a module that can be imported as-is or as sub-module of the worker package
    mod_spec = importlib.util.find_spec(module_name_string) or importlib.util.find_spec(
        "microengine.{0}".format(module_name_string))
    if mod_spec is None:
        raise Exception("Scanner backend `{0}` cannot be imported as a python module.".format(backend))

    # have valid module that can be imported, so import it.
    scanner_module = importlib.import_module(mod_spec.name)

    # find Scanner class in this module
    if hasattr(scanner_module, "Scanner"):
        scanner_class = scanner_module.Scanner
    elif len(backend_list) == 2 and hasattr(scanner_module, backend_list[1]):
        scanner_class = getattr(scanner_module, backend_list[1])
    else:
        raise Exception("No scanner backend found {0}".format(backend))

    return scanner_module.__name__, scanner_class


@click.command()
@click.option('--log', default='WARNING',
              help='Logging level')
@click.option('--redis-addr', envvar='REDIS_ADDR', default='localhost:6379',
              help='Address (host:port) of polyswarmd instance')
@click.option('--queue', envvar='QUEUE', required=True,
              help='Queue to listen for jobs on')
@click.option('--api-key', envvar='API_KEY', default='',
              callback=validate_apikey,
              help='API key to use with polyswarmd')
@click.option('--backend', envvar='BACKEND', required=True,
              help='Backend to use')
@click.option('--testing', default=0,
              help='Activate testing mode for integration testing, respond to N bounties and N offers then exit')
@click.option('--log-format', default='text',
              help='Log format. Can be `json` or `text` (default)')
def main(log, redis_addr, queue, api_key, backend, testing, log_format):
    """Entrypoint for the worker driver

    Args:
        log (str): Logging level
        redis_addr (str): Address of redis
        polyswarmd_addr (str): Address of polyswarmd
        backend (str): Backend implementation to use
        api_key(str): API key to use with polyswarmd
        testing (int): Mode to process N bounties then exit (optional)
        log_format (str): Format to output logs in. `text` or `json`
    """
    loglevel = getattr(logging, log.upper(), None)
    if not isinstance(loglevel, int):
        logging.error('invalid log level')
        sys.exit(-1)

    logger_name, scanner_class = choose_backend(backend)

    scanner = scanner_class()
    init_logging(['worker', 'microengine', logger_name], log_format, loglevel)

    worker = Worker(redis_addr, queue, api_key, testing, scanner)
    worker.run()


if __name__ == '__main__':
    main()
