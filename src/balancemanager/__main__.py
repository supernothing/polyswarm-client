import click
import logging
import sys
import functools

from balancemanager import Deposit, Withdraw, Maintainer, DepositStake, WithdrawStake, ViewBalance, ViewStake
from polyswarmclient.config import init_logging, validate_apikey
from polyswarmclient import Client

logger = logging.getLogger(__name__)


def validate_optional_transfer_amount(ctx, param, value):
    if value != 0:
        return value
    else:
        raise click.BadParameter('must be greater than 0')


def validate_transfer_amount(ctx, param, value):
    if value is None or value > 0:
        return value
    else:
        raise click.BadParameter('must be greater than 0')


def polyswarm_client(func):
    @click.option('--polyswarmd-addr', envvar='POLYSWARMD_ADDR', default='api.polyswarm.network/v1/default',
                  help='Address (host:port) of polyswarmd instance')
    @click.option('--keyfile', envvar='KEYFILE', type=click.Path(), default=None,
                  help='Keystore file containing the private key to use with this balancemanager')
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
@click.option('--client-log', default='WARNING',
              help='PolySwarm Client log level')
@click.option('--log-format', default='text',
              help='Log format. Can be `json` or `text` (default)')
def cli(log, client_log, log_format):
    """
    Entrypoint for the balance manager driver

    """
    loglevel = getattr(logging, log.upper(), None)
    clientlevel = getattr(logging, client_log.upper(), None)
    if not isinstance(loglevel, int) or not isinstance(clientlevel, int):
        logging.error('invalid log level')
        sys.exit(-1)

    init_logging(['balancemanager'], log_format, loglevel)
    init_logging(['polyswarmclient'], log_format, clientlevel)


@cli.command()
@polyswarm_client
@click.option('--denomination', type=click.Choice(['nct', 'nct-gwei', 'nct-wei']), default='nct')
@click.option('--all', is_flag=True)
@click.argument('amount', type=float, callback=validate_transfer_amount, required=False, default=None)
def deposit(polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, denomination, all, amount):
    """
    Deposit NCT into a sidechain
    """
    if amount is None and not all:
        raise click.BadArgumentUsage('Must specify either an amount or --all')
    client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
    d = Deposit(client, denomination, all, amount, testing=testing)
    d.run_oneshot()
    sys.exit(d.exit_code)


@cli.command()
@polyswarm_client
@click.option('--denomination', type=click.Choice(['nct', 'nct-gwei', 'nct-wei']), default='nct')
@click.option('--all', is_flag=True)
@click.argument('amount', type=float, callback=validate_transfer_amount, required=False, default=None)
def withdraw(polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, denomination, all, amount):
    """
    Withdraw NCT from a sidechain
    """
    if amount is None and not all:
        raise click.BadArgumentUsage('Must specify either an amount or --all')
    client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
    w = Withdraw(client, denomination, all, amount, testing=testing)
    w.run_oneshot()
    sys.exit(w.exit_code)


@cli.command('deposit-stake')
@polyswarm_client
@click.option('--denomination', type=click.Choice(['nct', 'nct-gwei', 'nct-wei']), default='nct')
@click.option('--all', is_flag=True)
@click.option('--chain', type=click.Choice(['side', 'home']), default='side')
@click.argument('amount', type=float, callback=validate_transfer_amount, required=False, default=None)
def deposit_stake(polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, denomination, all, chain, amount):
    """
    Deposit NCT into the ArbiterStaking contract
    """
    if amount is None and not all:
        raise click.BadArgumentUsage('Must specify either an amount or --all')
    client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
    d = DepositStake(client, denomination, all, amount, testing=testing, chain=chain)
    d.run_oneshot()
    sys.exit(d.exit_code)


@cli.command('withdraw-stake')
@polyswarm_client
@click.option('--denomination', type=click.Choice(['nct', 'nct-gwei', 'nct-wei']), default='nct')
@click.option('--all', is_flag=True)
@click.option('--chain', type=click.Choice(['side', 'home']), default='side')
@click.argument('amount', type=float, callback=validate_transfer_amount, required=False, default=None)
def withdraw_stake(polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, denomination, all, chain, amount):
    """
    Withdraw NCT from the ArbiterStaking contract
    """
    if amount is None and not all:
        raise click.BadArgumentUsage('Must specify either an amount or --all')
    client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
    w = WithdrawStake(client, denomination, all, amount, testing=testing, chain=chain)
    w.run_oneshot()
    sys.exit(w.exit_code)


@cli.command()
@polyswarm_client
@click.option('--denomination', type=click.Choice(['nct', 'nct-gwei', 'nct-wei']), default='nct')
@click.option('--maximum', type=float, callback=validate_optional_transfer_amount, default=-1,
              help='Maximum allowable balance before triggering a withdraw from the sidechain')
@click.option('--withdraw-target', type=float, callback=validate_optional_transfer_amount, default=-1,
              help='The goal balance of the sidechain after the withdrawal')
@click.option('--confirmations', type=int, default=20,
              help='Number of block confirmations relay requires before approving the transfer')
@click.argument('minimum', type=float, callback=validate_transfer_amount)
@click.argument('refill-amount', type=float, callback=validate_transfer_amount)
def maintain(polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, denomination,
             maximum, withdraw_target, confirmations, minimum, refill_amount):
    """
    Maintain min/max NCT balance in sidechain
    """
    logger.info('Maintaining the minimum balance by depositing %s %s when it falls below %s %s',
                refill_amount,
                denomination,
                minimum,
                denomination)
    if maximum > 0 and withdraw_target < 0:
        logger.warning('Must set a withdraw target when using a maximum')
        return

    if maximum > 0 and 0 < withdraw_target < minimum:
        logger.warning('Withdraw-target must me more than minimum')
        return

    if 0 < maximum < minimum:
        logger.warning('Maximum must be more than minimum')
        return

    if maximum > 0 and withdraw_target > 0:
        logger.info('Maintaining the minimum balance by withdrawing to %s %s when it exceeds %s %s',
                    withdraw_target,
                    denomination,
                    maximum,
                    denomination)

    client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
    Maintainer(client, denomination, confirmations, minimum, refill_amount, maximum, withdraw_target, testing).run()


@cli.command('view-balance')
@polyswarm_client
@click.option('--denomination', type=click.Choice(['nct', 'nct-gwei', 'nct-wei']), default='nct')
@click.argument('chain', type=click.Choice(['side', 'home']), required=True)
def view_balance(polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, denomination, chain):
    client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
    balance = ViewBalance(client, denomination, chain)
    balance.run_oneshot()
    sys.exit(balance.exit_code)


@cli.command('view-stake')
@polyswarm_client
@click.option('--denomination', type=click.Choice(['nct', 'nct-gwei', 'nct-wei']), default='nct')
@click.argument('chain', type=click.Choice(['side', 'home']), required=True)
def view_stake(polyswarmd_addr, keyfile, password, api_key, testing, insecure_transport, denomination, chain):
    client = Client(polyswarmd_addr, keyfile, password, api_key, testing > 0, insecure_transport)
    balance = ViewStake(client, denomination, chain)
    balance.run_oneshot()
    sys.exit(balance.exit_code)


if __name__ == '__main__':
    cli(dict())
