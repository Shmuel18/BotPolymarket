# executor.py
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from config import CLOB_URL, API_KEY, API_SECRET, API_PASSPHRASE, PRIVATE_KEY, CHAIN_ID

class OrderExecutor:
    def __init__(self):
        # יצירת אובייקט קרדנציאלים - זה השלב שהיה חסר
        creds = ApiCreds(
            api_key=API_KEY,
            api_secret=API_SECRET,
            api_passphrase=API_PASSPHRASE
        )
        
        # אתחול הלקוח בצורה תקינה
        # שים לב: הפרמטר 'key' מקבל את המפתח הפרטי (Private Key) לצורך חתימה
        self.client = ClobClient(
            host=CLOB_URL,
            key=PRIVATE_KEY,
            chain_id=CHAIN_ID,
            creds=creds
        )

    def execute_trade(self, clob_token_id, side, size, price):
        """
        מבצע פקודת מסחר בבורסה.
        """
        try:
            # שימוש ב-create_order ליצירה ושליחה של הפקודה
            return self.client.create_order(
                clob_token_id=clob_token_id,
                side=side,
                size=size,
                price=price,
                order_type='limit'
            )
        except Exception as e:
            print(f"Trade failed: {e}")
            return None