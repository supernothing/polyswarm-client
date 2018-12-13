import logging

logger = logging.getLogger(__name__)  # Initialize logger


class StakingClient(object):
    def __init__(self, client):
        self.__client = client
        self.parameters = {}

    async def get_parameters(self, chain, api_key=None):
        """Get staking parameters from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing staking parameters
        """
        success, result = await self.__client.make_request('GET', '/staking/parameters', chain, api_key=api_key)
        if not success:
            raise Exception('Error retrieving staking parameters')
        self.parameters[chain] = result

    async def get_total_balance(self, chain, api_key=None):
        """Get total staking balance from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing staking balance
        """
        path = '/balances/{0}/staking/total'.format(self.__client.account)
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        return int(result)

    async def get_withdrawable_balance(self, chain, api_key=None):
        """Get withdrawable staking balance from polyswarmd

        Args:
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing staking balance
        """
        path = '/balances/{0}/staking/withdrawable'.format(self.__client.account)
        success, result = await self.__client.make_request('GET', path, chain, api_key=api_key)
        return int(result)

    async def post_deposit(self, amount, chain, api_key=None):
        """Post a deposit to the staking contract

        Args:
            amount (int): The amount to stake
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        deposit = {
            'amount': str(amount),
        }
        success, results = await self.__client.make_request_with_transactions('POST', '/staking/deposit', chain,
                                                                              json=deposit, api_key=api_key)
        if not success or 'deposits' not in results:
            logger.error('Expected deposit, received', extra={'extra': results})

        return results.get('deposits', [])

    async def post_withdraw(self, amount, chain, api_key=None):
        """Post a withdrawal to the staking contract

        Args:
            amount (int): The amount to withdraw
            chain (str): Which chain to operate on
            api_key (str): Override default API key
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        withdrawal = {
            'amount': str(amount),
        }
        success, results = await self.__client.make_request_with_transactions('POST', '/staking/withdraw', chain,
                                                                              json=withdrawal, api_key=api_key)
        if not success or 'withdrawals' not in results:
            logger.error('Expected withdrawal, received', extra={'extra': results})

        return results.get('withdrawals', [])
