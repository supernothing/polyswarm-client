import logging

logger = logging.getLogger(__name__)  # Initialize logger


class RelayClient(object):
    def __init__(self, client):
        self.__client = client
        self.parameters = {}

    async def post_deposit(self, amount):
        """Post a deposit to the relay contract

        Args:
            amount (int): The amount to deposit to the sidechain
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        deposit = {
            'amount': str(amount),
        }
        success, results = await self.__client.make_request_with_transactions('POST', '/relay/deposit', 'home', json=deposit)
        if not success or 'transfers' not in results:
            logger.error('Expected deposit to relay', extra={'extra': results})

        return results.get('transfers', [])

    async def post_withdraw(self, amount):
        """Post a withdrawal to the relay contract

        Args:
            amount (int): The amount to withdraw from the sidechain
            chain (str): Which chain to operate on
        Returns:
            Response JSON parsed from polyswarmd containing emitted events
        """
        withdrawal = {
            'amount': str(amount),
        }
        success, results = await self.__client.make_request_with_transactions('POST', '/relay/withdrawal', chain='side', json=withdrawal)
        if not success or 'transfers' not in results:
            logger.error('Expected withdrawl from relay', extra={'extra': results})
            return {}

        return results.get('transfers', [])
