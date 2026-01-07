# main.py
import asyncio
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set

from .scanner import scan_polymarket_for_hierarchical_markets
from .ws_manager import WebSocketManager
from .logic import check_arbitrage
from .executor import OrderExecutor
from .config import MARKET_SCAN_INTERVAL

logger = logging.getLogger(__name__)

class PolymarketBot:
    """Main trading bot orchestrator."""
    
    def __init__(self):
        self.ws = WebSocketManager()
        self.executor: Optional[OrderExecutor] = None
        self.current_prices: Dict[str, float] = {}
        self.active_pairs: List[Dict] = []
        self.subscribed_tokens: Set[str] = set()
        self.last_scan_time = 0
        self.running = True
        self.shutdown_event = asyncio.Event()
        # State machine to prevent duplicate trades
        self.last_trade_attempt: Dict[str, float] = {}  # event_id -> timestamp
        self.trade_cooldown = 60  # seconds between trades on same event
        self.stats = {
            'opportunities_found': 0,
            'trades_executed': 0,
            'total_pnl': 0.0,
            'price_updates': 0
        }
    
    async def on_price_update(self, token_id: str, price: float) -> None:
        """Handle incoming price update from WebSocket.
        
        Args:
            token_id: Token ID that was updated
            price: New bid price
        """
        self.current_prices[token_id] = price
        self.stats['price_updates'] += 1
        
        # Check for arbitrage opportunities
        opportunities = check_arbitrage(self.active_pairs, self.current_prices)
        
        if opportunities:
            self.stats['opportunities_found'] += len(opportunities)
            for opp in opportunities:
                await self.handle_opportunity(opp)
    
    async def handle_opportunity(self, opportunity: Dict) -> None:
        """Process and potentially execute an arbitrage opportunity."""
        try:
            event_id = opportunity['event']
            current_time = asyncio.get_event_loop().time()
            
            # Check if we recently traded this event (prevent duplicates)
            if event_id in self.last_trade_attempt:
                time_since_last = current_time - self.last_trade_attempt[event_id]
                if time_since_last < self.trade_cooldown:
                    logger.debug(f"[SKIP] {event_id} - Cooldown active ({time_since_last:.0f}s ago)")
                    return
            
            logger.info(
                f"[OPPORTUNITY] {opportunity['event']} | "
                f"Profit: ${opportunity['profit_margin']:.4f} "
                f"({opportunity['profit_pct']:.2f}%) | "
                f"Strategy: {opportunity['strategy']}"
            )
            
            # Execute trade if executor is initialized
            if self.executor:
                # Update last attempt timestamp
                self.last_trade_attempt[event_id] = current_time
                
                # Calculate order size (5% of balance max, or $10 minimum)
                await self.executor.get_usdc_balance()
                order_size = max(10.0, self.executor.usdc_balance * 0.05) / opportunity['easy_price']
                
                logger.info(f"[EXECUTE] Attempting arbitrage trade with size: {order_size:.2f}")
                
                success = self.executor.execute_arbitrage(opportunity, order_size)
                
                if success:
                    self.stats['trades_executed'] += 1
                    profit = opportunity['profit_margin'] * order_size
                    self.stats['total_pnl'] += profit
                    logger.info(f"✅ [SUCCESS] Trade executed! Estimated profit: ${profit:.4f}")
                else:
                    logger.warning(f"⚠️ [FAILED] Trade execution failed for {event_id}")
            else:
                logger.warning("[WARNING] Executor not initialized - opportunity logged only")
                
        except Exception as e:
            logger.error(f"Error handling opportunity: {e}")
    
    async def scan_and_subscribe(self) -> bool:
        """Scan for hierarchical markets and subscribe to tokens.
        
        Returns:
            True if markets found and subscriptions successful
        """
        try:
            logger.info("[SCAN] Searching for hierarchical markets...")
            # Run blocking scan in thread to avoid blocking event loop
            markets = await asyncio.to_thread(scan_polymarket_for_hierarchical_markets)
            
            if not markets:
                logger.warning("[SCAN] No hierarchical markets found")
                return False
            
            # Build pairs from hierarchical markets
            self.active_pairs = []
            new_tokens = set()
            
            for event_title, market_data in markets.items():
                token_ids = market_data.get("clob_token_ids", [])
                
                # Create pairs for consecutive thresholds
                for i in range(len(token_ids) - 1):
                    pair = {
                        'event_title': event_title,
                        'parent_id': token_ids[i],
                        'child_id': token_ids[i + 1]
                    }
                    self.active_pairs.append(pair)
                    new_tokens.add(token_ids[i])
                    new_tokens.add(token_ids[i + 1])
            
            logger.info(
                f"[OK] Found {len(self.active_pairs)} pairs from {len(markets)} hierarchical markets"
            )
            logger.info(f"[INFO] Total unique tokens: {len(new_tokens)}")
            
            # Subscribe to tokens
            self.subscribed_tokens = new_tokens
            if self.ws.ws is None:
                logger.info("[CONNECT] Connecting to WebSocket...")
                if not await self.ws.connect():
                    logger.error("[ERROR] Failed to connect to WebSocket")
                    return False
            
            subscribed = await self.ws.subscribe_batch(list(new_tokens))
            logger.info(f"[CONNECT] Subscribed to {subscribed} tokens")
            
            return subscribed > 0
            
        except Exception as e:
            logger.error(f"[ERROR] Scanning markets: {e}")
            return False
    
    async def market_monitoring_loop(self) -> None:
        """Main monitoring loop - checks for market updates."""
        try:
            logger.info("[RUN] Starting market monitoring loop")
            await self.ws.receive_data(self.on_price_update)
        except asyncio.CancelledError:
            logger.info("[INFO] Market monitoring cancelled")
        except Exception as e:
            logger.error(f"[ERROR] Monitoring loop: {e}")
    
    async def periodic_rescan_loop(self) -> None:
        """Periodically scan for new markets (every hour)."""
        while self.running:
            try:
                await asyncio.wait_for(asyncio.sleep(MARKET_SCAN_INTERVAL), timeout=MARKET_SCAN_INTERVAL + 1)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            
            if not self.running:
                break
                
            try:
                logger.info("[RESCAN] Periodic market update...")
                await self.scan_and_subscribe()
            except Exception as e:
                logger.error(f"[ERROR] Rescan loop: {e}")
    
    async def stats_reporter_loop(self) -> None:
        """Periodically report bot statistics."""
        while self.running:
            try:
                await asyncio.wait_for(asyncio.sleep(300), timeout=301)  # Report every 5 minutes
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            
            if not self.running:
                break
                
            try:
                logger.info(
                    f"[STATS] Updates: {self.stats['price_updates']} | "
                    f"Opportunities: {self.stats['opportunities_found']} | "
                    f"Trades: {self.stats['trades_executed']} | "
                    f"P&L: ${self.stats['total_pnl']:.2f}"
                )
            except Exception as e:
                logger.error(f"[ERROR] Stats loop: {e}")
    
    def shutdown(self, signum, frame) -> None:
        """Handle shutdown signal gracefully."""
        logger.info("\n[SHUTDOWN] Ctrl+C detected - cleaning up...")
        self.running = False
    
    async def run(self) -> None:
        """Main bot execution method."""
        # Register signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        
        logger.info("\n" + "="*60)
        logger.info("[START] POLYMARKET ARBITRAGE BOT")
        logger.info(f"[TIME] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("[INFO] Press Ctrl+C to stop")
        logger.info("="*60 + "\n")
        
        # Initial market scan
        if not await self.scan_and_subscribe():
            logger.error("Failed to scan markets on startup")
            return
        
        # Create tasks with proper cancellation handling
        monitor_task = None
        rescan_task = None
        stats_task = None
        
        try:
            monitor_task = asyncio.create_task(self.market_monitoring_loop())
            rescan_task = asyncio.create_task(self.periodic_rescan_loop())
            stats_task = asyncio.create_task(self.stats_reporter_loop())
            
            # Main loop - check if running every 100ms
            while self.running:
                await asyncio.sleep(0.1)
                
            # If we exit the loop, shutdown was signaled
            logger.info("[SHUTDOWN] Shutting down tasks...")
            
        except KeyboardInterrupt:
            logger.info("[SHUTDOWN] Keyboard interrupt")
            self.running = False
        finally:
            # Ensure all tasks are cancelled
            self.running = False
            
            tasks_to_cancel = [t for t in [monitor_task, rescan_task, stats_task] if t]
            for task in tasks_to_cancel:
                if not task.done():
                    task.cancel()
            
            # Wait for cancellation
            if tasks_to_cancel:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            
            await self.cleanup()
    
    async def cleanup(self) -> None:
        """Clean up resources on shutdown."""
        logger.info("[CLEANUP] Closing connections...")
        await self.ws.close()
        
        logger.info(
            f"\n[FINAL STATS]\n"
            f"  Price Updates: {self.stats['price_updates']}\n"
            f"  Opportunities Found: {self.stats['opportunities_found']}\n"
            f"  Trades Executed: {self.stats['trades_executed']}\n"
            f"  Total P&L: ${self.stats['total_pnl']:.2f}\n"
        )
        logger.info("[DONE] Bot shutdown complete")


async def main():
    """Entry point for the bot."""
    bot = PolymarketBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())