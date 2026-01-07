# ws_manager.py
import asyncio
import websockets
import json
import logging
from typing import Callable, Dict, Optional, List, Any
from .config import CLOB_WS_URL, WS_PING_INTERVAL, WS_PING_TIMEOUT, MAX_RETRIES

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connection to Polymarket CLOB for real-time price updates."""
    
    def __init__(self):
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.prices: Dict[str, float] = {}
        self.subscribed_tokens: set = set()
        self.reconnect_count = 0

    async def connect(self, retry_count: int = 0) -> bool:
        """Establish WebSocket connection with exponential backoff retry.
        
        Args:
            retry_count: Current retry attempt number
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to CLOB WebSocket: {CLOB_WS_URL}")
            self.ws = await asyncio.wait_for(
                websockets.connect(
                    CLOB_WS_URL,
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=WS_PING_TIMEOUT,
                    close_timeout=10
                ),
                timeout=15
            )
            logger.info("[CONNECT] Connected to CLOB WebSocket")
            self.reconnect_count = 0
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"WebSocket connection timeout (attempt {retry_count + 1})")
            if retry_count < MAX_RETRIES:
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                return await self.connect(retry_count + 1)
            return False
            
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket connection failed: {e}")
            if retry_count < MAX_RETRIES:
                await asyncio.sleep(2 ** retry_count)
                return await self.connect(retry_count + 1)
            return False
            
        except Exception as e:
            logger.error(f"Unexpected connection error: {e}")
            return False

    async def subscribe(self, clob_token_id: str) -> bool:
        """Subscribe to market updates for a specific token.
        
        Args:
            clob_token_id: Token ID to subscribe to
        
        Returns:
            True if subscription sent successfully
        """
        if not self.ws:
            logger.warning(f"Cannot subscribe - WebSocket not connected")
            return False
        
        if clob_token_id in self.subscribed_tokens:
            return True
        
        try:
            payload = {
                "type": "market",
                "assets_ids": [clob_token_id]
            }
            await self.ws.send(json.dumps(payload))
            self.subscribed_tokens.add(clob_token_id)
            logger.debug(f"Subscribed to token: {clob_token_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to {clob_token_id}: {e}")
            return False
    
    async def subscribe_batch(self, token_ids: List[str]) -> int:
        """Subscribe to multiple tokens efficiently.
        
        Args:
            token_ids: List of token IDs to subscribe to
        
        Returns:
            Number of successful subscriptions
        """
        success_count = 0
        for token_id in token_ids:
            if await self.subscribe(token_id):
                success_count += 1
        return success_count

    async def receive_data(self, callback: Callable) -> None:
        """Receive and process market data updates.
        
        Args:
            callback: Async function to call on each price update
        """
        if not self.ws:
            logger.error("Cannot receive data - WebSocket not connected")
            return
        
        try:
            async for message in self.ws:
                if not message:
                    continue
                
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.debug(f"Failed to parse JSON: {message[:100]}...")
                    continue
                
                # Handle both single message and message array
                messages = data if isinstance(data, list) else [data]
                
                for msg in messages:
                    if not isinstance(msg, dict):
                        continue
                    
                    # Extract best bid (highest bid price = best offer to buy)
                    if "bids" in msg and msg["bids"]:
                        try:
                            token_id = msg.get("asset_id")
                            bids = msg["bids"]
                            
                            # Validate bids array
                            if not isinstance(bids, list) or len(bids) == 0:
                                logger.debug(f"Empty bids for {token_id[:8] if token_id else 'unknown'}")
                                continue
                            
                            price = float(bids[0][0])
                            
                            # Sanity check: price should be 0-1 for yes/no tokens
                            if not (0 <= price <= 1):
                                logger.warning(f"⚠️ Price sanity check FAILED: {price} for {token_id[:8] if token_id else 'unknown'} (expected 0-1)")
                                continue
                            
                            if token_id and price >= 0:
                                self.prices[token_id] = price
                                await callback(token_id, price)
                        except (ValueError, IndexError, TypeError) as e:
                            logger.debug(f"Error processing bid data: {e}")
                            continue
                            
        except asyncio.CancelledError:
            logger.info("WebSocket receive loop cancelled")
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    async def close(self) -> None:
        """Properly close WebSocket connection."""
        if self.ws:
            try:
                await asyncio.wait_for(self.ws.close(), timeout=2.0)
                logger.info("WebSocket closed")
            except asyncio.TimeoutError:
                logger.warning("WebSocket close timeout")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
            finally:
                self.ws = None