# logic.py
import logging
from typing import List, Dict, Any, Optional
from .config import PROFIT_THRESHOLD

logger = logging.getLogger(__name__)

def check_arbitrage(pairs: List[Dict[str, Any]], 
                    current_prices: Dict[str, float],
                    min_profit: float = PROFIT_THRESHOLD) -> List[Dict[str, Any]]:
    """Detect hierarchical arbitrage opportunities.
    
    Hierarchical Arbitrage Logic:
    If Market A has condition "Price > X" and Market B has "Price > Y" where Y > X,
    then logically: P(B) <= P(A) always (stricter condition = lower probability = lower price).
    
    If Price(B) > Price(A), we can:
    1. Buy YES on A (cheaper) and sell NO on B (expensive) for guaranteed profit
    2. Or: Buy YES on A and short YES on B
    
    Args:
        pairs: List of market pairs with hierarchical relationships
        current_prices: Current bid prices for all tokens
        min_profit: Minimum profit threshold to consider an opportunity
    
    Returns:
        List of detected arbitrage opportunities
    """
    opportunities = []
    
    if not pairs or not current_prices:
        logger.debug("No pairs or prices available for arbitrage check")
        return opportunities

    for pair in pairs:
        try:
            parent_id = pair.get('parent_id')  # Lower threshold (e.g., "BTC > 100k")
            child_id = pair.get('child_id')    # Higher threshold (e.g., "BTC > 105k")
            event_title = pair.get('event_title', 'Unknown')
            parent_all_tokens = pair.get('parent_all_tokens', [])
            child_all_tokens = pair.get('child_all_tokens', [])
            
            if not parent_id or not child_id:
                logger.warning(f"Invalid pair structure: {pair}")
                continue
            
            price_parent = current_prices.get(parent_id)
            price_child = current_prices.get(child_id)

            # Skip if we don't have both prices
            if price_parent is None or price_child is None:
                continue
            
            # Validate price ranges
            if not (0 <= price_parent <= 1 and 0 <= price_child <= 1):
                logger.debug(f"Invalid price range - Parent: {price_parent}, Child: {price_child}")
                continue
            
            # CORRECT Arbitrage detection:
            # Price(harder/child condition) should ALWAYS be <= Price(easier/parent condition)
            # If Price(child) > Price(parent), it's MISPRICED → arbitrage opportunity
            # Strategy: BUY parent (cheap), SELL child (expensive)
            profit = price_child - price_parent  # How much we profit (child should be less!)
            
            if profit >= min_profit:
                opportunity = {
                    'event': event_title,
                    'easy_condition_id': parent_id,  # Buy this (should be cheaper)
                    'hard_condition_id': child_id,   # Sell this (incorrectly expensive)
                    'easy_price': price_parent,
                    'hard_price': price_child,
                    'easy_condition_all_tokens': parent_all_tokens,  # For NO token lookup
                    'hard_condition_all_tokens': child_all_tokens,   # For NO token lookup
                    'profit_margin': profit,
                    'profit_pct': (profit / price_child * 100) if price_child > 0 else 0,
                    'strategy': 'BUY parent (easy/cheap) + BUY NO on child (hard/expensive) = PROFIT'
                }
                opportunities.append(opportunity)
                logger.info(f"[ARBITRAGE] {event_title} | "
                          f"Profit: ${profit:.4f} ({opportunity['profit_pct']:.2f}%)")
                
        except Exception as e:
            logger.error(f"Error checking pair {pair}: {e}")
            continue
    
    if opportunities:
        logger.info(f"Total opportunities found: {len(opportunities)}")
    
    return sorted(opportunities, key=lambda x: x['profit_margin'], reverse=True)