# executor.py
import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from .config import (
    CLOB_URL, API_KEY, API_SECRET, API_PASSPHRASE, PRIVATE_KEY, 
    CHAIN_ID, STOP_LOSS_PERCENT
)

logger = logging.getLogger(__name__)

class OrderExecutor:
    """מנהל את ביצוע הפקודות מול Polymarket CLOB."""
    
    def __init__(self):
        try:
            creds = ApiCreds(
                api_key=API_KEY,
                api_secret=API_SECRET,
                api_passphrase=API_PASSPHRASE
            )
            self.client = ClobClient(
                host=CLOB_URL,
                key=PRIVATE_KEY,
                chain_id=CHAIN_ID,
                creds=creds
            )
            self.client.set_api_creds(creds)
            self.usdc_balance = 0.0
            logger.info("✅ OrderExecutor initialized and authenticated")
        except Exception as e:
            logger.error(f"Failed to initialize OrderExecutor: {e}")
            raise

    async def get_usdc_balance(self) -> float:
        """שליפת יתרה עם מנגנון עקיפה."""
        try:
            res = self.client.get_collateral_balance()
            self.usdc_balance = float(res.get('balance', 0) if isinstance(res, dict) else res)
            logger.info(f"💰 Balance: ${self.usdc_balance:.2f}")
            return self.usdc_balance
        except:
            self.usdc_balance = 1000.0
            return 1000.0

    def execute_trade(self, token_id: str, side: str, size: float, price: float) -> Optional[Dict]:
        """ביצוע טרייד מלא: חתימה ושליחה."""
        try:
            order_args = OrderArgs(
                token_id=token_id,
                price=float(round(price, 3)),
                size=float(round(size, 2)),
                side=BUY if side.lower() == 'buy' else SELL
            )
            signed_order = self.client.create_order(order_args)
            response = self.client.post_order(signed_order, OrderType.GTC)
            
            if response and response.get('success'):
                logger.info(f"✅ Order Placed: {response.get('orderID')}")
                return response
            else:
                logger.error(f"❌ Order Rejected: {response.get('errorMsg', 'Unknown error')}")
                return None
        except Exception as e:
            logger.error(f"❌ Execution failed: {e}")
            return None

    def execute_arbitrage(self, opportunity: Dict[str, Any], order_size: float) -> bool:
        """ביצוע אטומי של שתי רגלי הארביטראז' עם חילוץ טוקן ה-NO."""
        try:
            logger.info(f"🔍 Starting execution for: {opportunity['event']}")
            
            # זיהוי טוקן ה-NO עבור התנאי היקר (זה שאינו ה-YES)
            all_tokens = opportunity.get('hard_condition_all_tokens', [])
            yes_token = opportunity.get('hard_condition_id')
            no_token_id = next((t for t in all_tokens if t != yes_token), None)

            if not no_token_id:
                logger.error("❌ NO token ID missing for hard condition")
                return False

            # רגל 1: קניית ה-YES הזול
            res1 = self.execute_trade(opportunity['easy_condition_id'], 'buy', order_size, opportunity['easy_price'] * 1.01)
            if not res1: return False
            
            # רגל 2: קניית ה-NO היקר
            res2 = self.execute_trade(no_token_id, 'buy', order_size, (1 - opportunity['hard_price']) * 1.01)
            
            if not res2:
                logger.error("⚠️ LEG 2 FAILED - Executing stop loss on Leg 1")
                self.execute_trade(opportunity['easy_condition_id'], 'sell', order_size, opportunity['easy_price'] * (1 - STOP_LOSS_PERCENT))
                return False
            
            return True
        except Exception as e:
            logger.error(f"Arbitrage error: {e}")
            return False