from py_clob_client.client import ClobClient
from config import API_KEY, API_SECRET, API_PASSPHRASE

class OrderExecutor:
    def __init__(self):
        self.client = ClobClient(
            ApiKey=API_KEY,
            ApiSecret=API_SECRET,
            ApiPassphrase=API_PASSPHRASE
        )

    async def execute_trade(self, clob_token_id, side, size, price):
        """
        Executes a trade on Polymarket CLOB.
        """
        try:
            order = await self.client.new_order(
                clob_token_id=clob_token_id,
                side=side,
                size=size,
                price=price,
                order_type='limit',
                time_in_force='gtc'
            )
            print(f"Order placed: {order}")
            return order
        except Exception as e:
            print(f"Error executing trade: {e}")
            return None
