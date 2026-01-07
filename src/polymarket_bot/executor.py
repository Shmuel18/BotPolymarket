# executor.py
import logging
from typing import Optional, Dict, Any
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from .config import (
    CLOB_URL, API_KEY, API_SECRET, API_PASSPHRASE, PRIVATE_KEY, 
    CHAIN_ID, STOP_LOSS_PERCENT, FUNDER_ADDRESS
)

logger = logging.getLogger(__name__)

class OrderExecutor:
    """מנהל פקודות עבור ארנקי Proxy (Magic/Email) לפי שלב 4 בתיעוד."""
    
    def __init__(self):
        try:
            creds = ApiCreds(
                api_key=API_KEY.strip() if API_KEY else "",
                api_secret=API_SECRET.strip() if API_SECRET else "",
                api_passphrase=API_PASSPHRASE.strip() if API_PASSPHRASE else ""
            )
            
            # אתחול עם ה-Proxy Wallet כ-Funder
            self.client = ClobClient(
                host=CLOB_URL,
                key=PRIVATE_KEY,
                chain_id=CHAIN_ID,
                creds=creds,
                signature_type=1, # חובה למשתמשי אימייל
                funder=FUNDER_ADDRESS # הכתובת 0x6f01... מה-env
            )
            
            self.client.set_api_creds(creds)
            self.usdc_balance = 0.0
            
            logger.info(f"🔑 Signer Wallet: {self.client.get_address()}")
            logger.info(f"💰 Funder Wallet (Proxy): {FUNDER_ADDRESS}")
            logger.info("✅ OrderExecutor initialized with POLY_PROXY support")
        except Exception as e:
            logger.error(f"Failed to initialize: {e}"); raise

    async def get_usdc_balance(self) -> float:
        """בדיקת יתרה אמיתית מה-API."""
        try:
            # נסיון לקבל יתרה אמיתית
            balance_info = self.client.get_balance_allowance()
            if balance_info and 'balance' in balance_info:
                self.usdc_balance = float(balance_info['balance'])
                logger.info(f"💰 Real USDC Balance: ${self.usdc_balance:.2f}")
            else:
                # אם לא מצליח, נשתמש בערך דיפולט נמוך
                self.usdc_balance = 40.0
                logger.warning(f"⚠️ Could not fetch real balance, using default: ${self.usdc_balance}")
        except Exception as e:
            # אם יש שגיאה, נשתמש בערך דיפולט
            self.usdc_balance = 40.0
            logger.warning(f"⚠️ Error fetching balance: {e}, using default: ${self.usdc_balance}")
        return self.usdc_balance

    def execute_trade(self, token_id: str, side: str, size: float, price: float) -> Optional[Dict]:
        """ביצוע טרייד עם חתימת Proxy (מתאים למשתמשי אימייל)."""
        try:
            order_args = OrderArgs(
                token_id=token_id,
                price=float(round(price, 3)),
                size=float(round(size, 2)),
                side=BUY if side.lower() == 'buy' else SELL
            )
            
            # יצירת הפקודה (כאן מתבצעת החתימה עם signature_type=1)
            signed_order = self.client.create_order(order_args)
            
            logger.info(f"🚀 Posting {side.upper()} order via Proxy for {token_id[:8]}...")
            response = self.client.post_order(signed_order, OrderType.GTC)
            
            if response and response.get('success'):
                logger.info(f"✅ SUCCESS: Order {response.get('orderID')}")
                return response
            else:
                error_msg = response.get('errorMsg', 'Unknown error')
                logger.error(f"❌ Rejected: {error_msg}")
                return None
        except Exception as e:
            logger.error(f"❌ Execution failed: {e}")
            return None

    def execute_arbitrage(self, opportunity: Dict[str, Any], order_size: float) -> bool:
        """ביצוע שתי רגלי הארביטראז'."""
        logger.info(f"🔍 Starting Arbitrage: {opportunity['event']}")
        
        all_tokens = opportunity.get('hard_condition_all_tokens', [])
        yes_token = opportunity.get('hard_condition_id')
        no_token_id = next((t for x in all_tokens for t in (x if isinstance(x, list) else [x]) if t != yes_token), None)

        if not no_token_id:
            logger.error("❌ Could not find NO token for hard leg")
            return False

        # רגל 1
        res1 = self.execute_trade(opportunity['easy_condition_id'], 'buy', order_size, opportunity['easy_price'] * 1.01)
        if not res1: return False
        
        # רגל 2
        res2 = self.execute_trade(no_token_id, 'buy', order_size, (1 - opportunity['hard_price']) * 1.01)
        if not res2:
            logger.error("⚠️ Leg 2 failed - Order mismatch risk!")
            return False
            
        return True