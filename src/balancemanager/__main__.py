import click
import logging
import sys
import functools

from balancemanager import Deposit, Withdraw, Maintainer
from polyswarmclient.config import init_logging, validate_apikey
from polyswarmclient import Client

logger = logging.getLogger(__name__)


def validate_optional_transfer_amount(ctx, param, value):
    if value != 0:
        return value
    else:
        raise click.BadParameter('must be greater than 0')


def validate_transfer_amount(ctx, param, value):
    if value > 0:
        return value
    else:
        raise click.BadParameter('must be greater than 0')


def polyswarm_client(func):
    @click.option('--polyswarmd-addr', envvar='POLYSWARMD_ADDR', default='localhost:31337',
                  help='Address (host:port) of polyswarmd instance')
    @click.option('--keyfile', envvar='KEYFILE', type=click.Path(), default=None,
                  help='Keystore file containing the private key to use with this microengine')
    @click.option('--password', envvar='PASSWORD', prompt=True, hide_input=True,
                  help='Password to decrypt the keyfile with')
    @click.option('--api-key', envvar='API_KEY', default='',
                  callback=validate_apikey,
                  help='API key to use with polyswarmd')
    @click.option('--testing', default=0,
                  help='Activate testing mode for integration testing, trigger N balances to the sidechain then exit')
    @click.option('--insecure-transport', is_flag=True,
                  help='Connect to polyswarmd via http:// and ws://, mutually exclusive with --api-key')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@click.group()
@click.option('--log', default='WARNING',
              help='Logging level')
@click.option('--log-format', default='text',
              help='Log format. Can be `json` or `text` (default)')
@click.pass_context
def cli(ctx, log, log_format):
    """
    Entrypoint for the balance manager driver
    """
    loglevel = getattr(logging, log.upper(), None)
    if not isinstance(loglevel, int):
        logging.error('invalid log level')
        sys.exit(-1)

    init_logging(['balancemanager'], log_format, loglevel)


@cli.command()
@polyswarm_client
@click.argument('amount', type=float, callback=validate_transfer_amount)
@click.pass_context
def deposit(ctx, polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, amount):
    """
    Entrypoint to deposit NCT into a sidechain

    Args:
        amount (float): Amount of Nectar (NCT) to transfer
    """
    client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
    d = Deposit(client, amount, testing=testing)
    d.run_oneshot()
    sys.exit(d.exit_code)


@cli.command()
@polyswarm_client
@click.argument('amount', type=float, callback=validate_transfer_amount)
@click.pass_context
def withdraw(ctx, polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, amount):
    """
    Entrypoint to withdraw NCT from a sidechain into the homechain

    Args:
        amount (float): Amount of Nectar (NCT) to transfer
    """
    client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
    w = Withdraw(client, amount, testing=testing)
    w.run_oneshot()
    sys.exit(w.exit_code)


@cli.command()
@polyswarm_client
@click.option('--maximum', type=float, callback=validate_optional_transfer_amount, default=-1,
              help='Maximum allowable balance before triggering a withdraw from the sidechain')
@click.option('--withdraw-target', type=float, callback=validate_optional_transfer_amount, default=-1,
              help='The goal balance of the sidechain after the withdrawal')
@click.option('--confirmations', type=int, default=20,
              help='Number of block confirmations relay requires before approving the transfer')
@click.argument('minimum', type=float, callback=validate_transfer_amount)
@click.argument('refill-amount', type=float, callback=validate_transfer_amount)
@click.pass_context
def maintain(ctx, polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, maximum, withdraw_target,
             confirmations, minimum, refill_amount):
    """
    Entrypoint to withdraw NCT from a sidechain into the homechain

    Args:
        minimum (float): Value of NCT on sidechain where you want to transfer more NCT
        refill-amount (float): Value of NCT to transfer anytime the balance falls below the minimum
    """
    logger.info('Maintaining the minimum balance by depositing %s NCT when it falls below %s NCT', refill_amount,
                minimum)
    if maximum > 0 and withdraw_target < 0:
        logger.warning('Must set a withdraw target when using a maximum')
        return

    if maximum > 0 and withdraw_target > 0 and withdraw_target < minimum:
        logger.warning('Withdraw-target must me more than minimum')
        return

    if maximum > 0 and maximum < minimum:
        logger.warning('Maximum must be more than minimum')
        return

    if maximum > 0 and withdraw_target > 0:
        logger.info('Maintaining the maximum balance by withdrawing to %s NCT when it exceeds %s NCT', withdraw_target,
                    maximum)

    client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
    Maintainer(client, confirmations, minimum, refill_amount, maximum, withdraw_target, testing).run()


if __name__ == "__main__":
    cli(dict())
