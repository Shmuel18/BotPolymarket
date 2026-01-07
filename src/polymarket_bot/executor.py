# executor.py
import logging
import asyncio
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from datetime import datetime
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from .config import (
    CLOB_URL, API_KEY, API_SECRET, API_PASSPHRASE, PRIVATE_KEY, 
    CHAIN_ID, MAX_USDC_ALLOCATION, SLIPPAGE_TOLERANCE, ORDER_TIMEOUT,
    MIN_LIQUIDITY, STOP_LOSS_PERCENT
)

logger = logging.getLogger(__name__)

@dataclass
class Order:
    """Represents a placed order."""
    order_id: str
    token_id: str
    side: str
    size: float
    price: float
    status: str
    timestamp: datetime
    
@dataclass
class ArbitrageTransaction:
    """Represents a complete arbitrage transaction (both legs)."""
    transaction_id: str
    event: str
    leg1_order_id: Optional[str] = None
    leg2_order_id: Optional[str] = None
    leg1_status: str = 'pending'
    leg2_status: str = 'pending'
    entry_price: float = 0.0
    exit_price: float = 0.0
    profit_margin: float = 0.0
    order_size: float = 0.0
    usdc_invested: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
class OrderExecutor:
    """Handles order execution for Polymarket arbitrage trades."""
    
    def __init__(self):
        """Initialize OrderExecutor with API credentials."""
        try:
            # Validate credentials
            if not all([API_KEY, API_SECRET, API_PASSPHRASE, PRIVATE_KEY]):
                raise ValueError("Missing required API credentials")
            
            # Create credentials object
            creds = ApiCreds(
                api_key=API_KEY,
                api_secret=API_SECRET,
                api_passphrase=API_PASSPHRASE
            )
            
            # Initialize CLOB client
            self.client = ClobClient(
                host=CLOB_URL,
                key=PRIVATE_KEY,
                chain_id=CHAIN_ID,
                creds=creds
            )
            
            self.orders: Dict[str, Order] = {}
            self.transactions: Dict[str, ArbitrageTransaction] = {}
            self.usdc_balance: float = 0.0
            logger.info("✅ OrderExecutor initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OrderExecutor: {e}")
            raise
    
    async def get_usdc_balance(self) -> float:
        """Get current USDC balance from wallet.
        
        Returns:
            USDC balance or 0.0 if unable to fetch
        """
        try:
            # Try to get balance from CLOB API
            balance = self.client.get_balance("USDC")
            self.usdc_balance = balance if balance else 0.0
            logger.info(f"💰 Current USDC balance: ${self.usdc_balance:.2f}")
            return self.usdc_balance
        except Exception as e:
            logger.warning(f"Failed to fetch USDC balance: {e}")
            return self.usdc_balance

    def execute_trade(self, clob_token_id: str, side: str, size: float, 
                      price: float, order_type: str = 'limit') -> Optional[Dict[str, Any]]:
        """Execute a single limit order with validation.
        
        Args:
            clob_token_id: Token ID to trade
            side: 'buy' or 'sell'
            size: Number of shares to trade
            price: Limit price (0-1 for yes/no tokens)
            order_type: Order type ('limit' or 'market')
        
        Returns:
            Order details if successful, None if failed
        """
        try:
            # Validate inputs
            if side not in ['buy', 'sell']:
                logger.error(f"Invalid side: {side}")
                return None
            
            if not (0 < price <= 1):
                logger.warning(f"Price {price} outside valid range (0, 1]")
                return None
            
            if size <= 0:
                logger.error(f"Invalid size: {size}")
                return None
            
            # Check minimum liquidity requirement
            min_cost = size * price
            if min_cost < MIN_LIQUIDITY / 100:  # Convert to minimal unit
                logger.warning(f"Order too small. Cost: ${min_cost:.2f} < Min: ${MIN_LIQUIDITY/100:.2f}")
                # Not a hard error, just warning
            
            logger.info(f"Executing {side.upper()} order: {size} shares @ ${price} (Type: {order_type})")
            
            # Create and submit order
            response = self.client.create_order(
                clob_token_id=clob_token_id,
                side=side,
                size=size,
                price=price,
                order_type=order_type
            )
            
            if response:
                order_id = response.get('id', response.get('orderId'))
                if order_id:
                    # Store order record
                    order = Order(
                        order_id=order_id,
                        token_id=clob_token_id,
                        side=side,
                        size=size,
                        price=price,
                        status='pending',
                        timestamp=datetime.now()
                    )
                    self.orders[order_id] = order
                    logger.info(f"✅ Order placed: {order_id}")
                    return response
            else:
                logger.error("Order response is empty")
                return None
                
        except Exception as e:
            logger.error(f"Trade execution failed for {clob_token_id}: {e}")
            return None
    
    def execute_arbitrage(self, opportunity: Dict[str, Any], order_size: float) -> bool:
        """Execute both legs of an arbitrage trade with atomic execution.
        
        CRITICAL: Both legs must succeed or both must be cancelled.
        If leg 2 fails, leg 1 is automatically reversed (stop loss).
        
        Args:
            opportunity: Arbitrage opportunity dict from logic.check_arbitrage
            order_size: Size of each leg (same for both)
        
        Returns:
            True if both orders placed and confirmed successfully
        """
        try:
            # 1. VALIDATE PRE-CONDITIONS
            logger.info(f"🔍 Validating arbitrage conditions for: {opportunity['event']}")
            
            # Check balance (now calculating for BUYING the easy condition)
            required_usdc = order_size * opportunity['easy_price']  # We BUY the cheaper one
            if self.usdc_balance < required_usdc:
                logger.error(f"❌ Insufficient balance. Need: ${required_usdc:.2f}, Have: ${self.usdc_balance:.2f}")
                return False
            
            # Check slippage tolerance
            if opportunity['profit_margin'] < SLIPPAGE_TOLERANCE:
                logger.warning(f"⚠️ Profit margin {opportunity['profit_margin']:.2%} < Slippage tolerance {SLIPPAGE_TOLERANCE:.2%}")
                return False
            
            # Add price buffer for better execution (1% above bid for buys)
            buy_price_with_buffer = min(opportunity['easy_price'] * 1.01, 0.99)
            no_token_price = 1.0 - opportunity['hard_price']  # NO price = 1 - YES price
            buy_no_price_with_buffer = min(no_token_price * 1.01, 0.99)
            
            # 2. EXECUTE LEG 1 (BUY EASY CONDITION - THE CHEAP ONE)
            logger.info(f"📈 LEG 1: Buying EASY condition (cheap) @ ${buy_price_with_buffer:.4f}")
            
            leg1 = self.execute_trade(
                clob_token_id=opportunity['easy_condition_id'],  # FIXED: Buy the CHEAP one
                side='buy',
                size=order_size,
                price=buy_price_with_buffer,
                order_type='limit'
            )
            
            if not leg1:
                logger.error("❌ LEG 1 FAILED - Aborting arbitrage")
                return False
            
            leg1_order_id = leg1.get('id', leg1.get('orderId'))
            logger.info(f"✅ LEG 1 SUCCESS: Order {leg1_order_id}")
            
            # 3. EXECUTE LEG 2 (BUY NO ON HARD CONDITION - THE EXPENSIVE ONE)
            # NOTE: We buy NO token (not sell YES) because we don't own YES tokens yet
            logger.info(f"📉 LEG 2: Buying NO on HARD condition (expensive) @ ${buy_no_price_with_buffer:.4f}")
            
            # Get NO token ID for the hard condition
            hard_no_token_id = self._get_no_token_id(
                opportunity.get('hard_condition_all_tokens', []),
                yes_token_id=opportunity.get('hard_condition_id')  # Exclude the YES token
            )
            if not hard_no_token_id:
                logger.error("❌ Cannot find NO token for hard condition")
                # Reverse leg 1
                self._execute_stop_loss(
                    leg1_order_id=leg1_order_id,
                    token_id=opportunity['easy_condition_id'],
                    order_size=order_size,
                    entry_price=buy_price_with_buffer
                )
                return False
            
            leg2 = self.execute_trade(
                clob_token_id=hard_no_token_id,  # FIXED: Buy NO token (not sell YES)
                side='buy',  # FIXED: Buy (not sell)
                size=order_size,
                price=buy_no_price_with_buffer,
                order_type='limit'
            )
            
            if not leg2:
                logger.error("❌ LEG 2 FAILED - EXECUTING STOP LOSS")
                
                # ATOMIC FAILURE: Reverse leg 1 by selling the EASY condition we bought
                # NOT the hard condition!
                self._execute_stop_loss(
                    leg1_order_id=leg1_order_id,
                    token_id=opportunity['easy_condition_id'],  # FIXED: Sell what we bought!
                    order_size=order_size,
                    entry_price=buy_price_with_buffer
                )
                return False
            
            leg2_order_id = leg2.get('id', leg2.get('orderId'))
            logger.info(f"✅ LEG 2 SUCCESS: Order {leg2_order_id}")
            
            # 4. RECORD TRANSACTION
            transaction = ArbitrageTransaction(
                transaction_id=f"{leg1_order_id}_{leg2_order_id}",
                event=opportunity['event'],
                leg1_order_id=leg1_order_id,
                leg2_order_id=leg2_order_id,
                leg1_status='confirmed',
                leg2_status='confirmed',
                entry_price=buy_price_with_buffer,  # What we paid for easy condition
                exit_price=buy_no_price_with_buffer,  # What we paid for NO on hard
                profit_margin=opportunity['profit_margin'],
                order_size=order_size,
                usdc_invested=required_usdc
            )
            self.transactions[transaction.transaction_id] = transaction
            
            # CORRECT profit calculation: profit_margin is already per-unit profit
            profit = opportunity['profit_margin'] * order_size
            logger.info(f"🎯 ✅ ARBITRAGE SUCCESS - Expected profit: ${profit:.4f}")
            return True
            
        except Exception as e:
            logger.error(f"Arbitrage execution failed: {e}")
            return False
    
    def _get_no_token_id(self, all_tokens: List[str], yes_token_id: Optional[str] = None) -> Optional[str]:
        """Get NO token ID from list of tokens.
        
        Args:
            all_tokens: List of token IDs [token1, token2]
            yes_token_id: Explicit YES token ID to exclude
        
        Returns:
            NO token ID or None
        """
        try:
            if not isinstance(all_tokens, list) or len(all_tokens) < 2:
                return None
            
            # If we know which is YES, return the other one
            if yes_token_id:
                for token in all_tokens:
                    if token != yes_token_id:
                        logger.debug(f"Found NO token (NOT {yes_token_id[:8]}): {token[:8]}")
                        return token
            
            # Fallback: assume NO is first, YES is second
            logger.debug(f"Using fallback: assuming all_tokens[0] is NO")
            return all_tokens[0]
            
        except Exception as e:
            logger.error(f"Failed to get NO token: {e}")
            return None
    
    def _execute_stop_loss(self, leg1_order_id: str, token_id: str, 
                          order_size: float, entry_price: float) -> bool:
        """Execute stop loss to reverse failed leg 1.
        
        Args:
            leg1_order_id: Order ID of leg 1 to reverse
            token_id: Token ID to reverse
            order_size: Size of order to reverse
            entry_price: Entry price for calculation
        
        Returns:
            True if stop loss executed
        """
        try:
            # Calculate stop loss price (e.g., entry - 5%)
            stop_loss_price = max(entry_price * (1 - STOP_LOSS_PERCENT), 0.01)
            
            logger.warning(f"🚨 Executing STOP LOSS: Selling {order_size} @ ${stop_loss_price}")
            
            response = self.execute_trade(
                clob_token_id=token_id,
                side='sell',
                size=order_size,
                price=stop_loss_price,
                order_type='market'  # Market order to ensure execution
            )
            
            if response:
                logger.warning(f"⚠️ Stop loss executed. Loss: ${(entry_price - stop_loss_price) * order_size:.4f}")
                return True
            else:
                logger.error("❌ Stop loss FAILED - Position may be open!")
                return False
                
        except Exception as e:
            logger.error(f"Stop loss execution failed: {e}")
            return False
    
    def get_order_status(self, order_id: str) -> Optional[str]:
        """Get status of a previously placed order.
        
        Args:
            order_id: Order ID to check
        
        Returns:
            Order status or None if not found
        """
        try:
            if order_id not in self.orders:
                return None
            return self.orders[order_id].status
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return None
    
    def get_transaction_pnl(self, transaction_id: str) -> Optional[float]:
        """Calculate P&L for a completed transaction.
        
        Args:
            transaction_id: Transaction ID
        
        Returns:
            Profit/loss in USDC or None if not found
        """
        try:
            if transaction_id not in self.transactions:
                return None
            
            tx = self.transactions[transaction_id]
            if tx.leg1_status != 'confirmed' or tx.leg2_status != 'confirmed':
                return None
            
            # P&L = (sell price - buy price) * size
            pnl = (tx.exit_price - tx.entry_price) * tx.order_size
            return pnl
            
        except Exception as e:
            logger.error(f"Failed to calculate P&L: {e}")
            return None
    
    def get_all_transactions(self) -> Dict[str, ArbitrageTransaction]:
        """Get all recorded transactions.
        
        Returns:
            Dictionary of all transactions
        """
        return self.transactions.copy()
    
    def get_transaction_summary(self) -> Dict[str, Any]:
        """Get summary of all transactions.
        
        Returns:
            Summary with total profit, count, etc.
        """
        total_profit = 0.0
        successful = 0
        failed = 0
        
        for tx in self.transactions.values():
            if tx.leg1_status == 'confirmed' and tx.leg2_status == 'confirmed':
                successful += 1
                pnl = self.get_transaction_pnl(tx.transaction_id)
                if pnl:
                    total_profit += pnl
            else:
                failed += 1
        
        return {
            'total_transactions': len(self.transactions),
            'successful': successful,
            'failed': failed,
            'total_profit_usdc': total_profit,
            'avg_profit_per_trade': total_profit / successful if successful > 0 else 0.0
        }