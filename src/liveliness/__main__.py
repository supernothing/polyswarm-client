import click
import logging
import sys

from polyswarmclient.config import init_logging
from polyswarmclient.liveliness import LivelinessChecker


@click.command()
@click.option('--log', default='WARNING',
              help='Logging level')
@click.option('--log-format', default='text',
              help='Log format. Can be `json` or `text` (default)')
@click.option('--loop-update-threshold', default=5,
              help='Maximum time since last loop iteration in polyswarm-client.Client before failing check')
@click.option('--average-bounty-wait-threshold', default=15,
              help='Maximum average time in blocks that bounties have been waiting before failing check')
def main(log, log_format, loop_update_threshold, average_bounty_wait_threshold):
    loglevel = getattr(logging, log.upper(), None)
    if not isinstance(loglevel, int):
        logging.error('invalid log level')
        sys.exit(-1)

    init_logging(['liveliness'], log_format, loglevel)

    liveliness_check = LivelinessChecker(loop_update_threshold, average_bounty_wait_threshold)
    sys.exit(0 if liveliness_check.check() else -1)


if __name__ == '__main__':
    main()
