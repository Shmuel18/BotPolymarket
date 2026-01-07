# ws_manager.py
import asyncio
import websockets
import json
import logging
from typing import Callable, Dict, Optional, List, Any
from .config import CLOB_WS_URL, WS_PING_INTERVAL, WS_PING_TIMEOUT, MAX_RETRIES

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.prices: Dict[str, float] = {}
        self.subscribed_tokens: set = set()

    async def connect(self, retry_count: int = 0) -> bool:
        try:
            logger.info(f"Connecting to CLOB WebSocket...")
            self.ws = await asyncio.wait_for(
                websockets.connect(CLOB_WS_URL, ping_interval=WS_PING_INTERVAL, ping_timeout=WS_PING_TIMEOUT),
                timeout=15
            )
            logger.info("[CONNECT] Connected to CLOB WebSocket")
            return True
        except Exception as e:
            if retry_count < MAX_RETRIES:
                await asyncio.sleep(2 ** retry_count)
                return await self.connect(retry_count + 1)
            return False

    async def subscribe(self, clob_token_ids: List[str]) -> bool:
        if not self.ws: return False
        try:
            to_subscribe = [str(tid) for tid in clob_token_ids if tid and str(tid) not in self.subscribed_tokens]
            if not to_subscribe: return True
            payload = {"type": "market", "operation": "subscribe", "assets_ids": to_subscribe}
            await self.ws.send(json.dumps(payload))
            self.subscribed_tokens.update(to_subscribe)
            return True
        except Exception as e:
            logger.error(f"❌ Subscription failed: {e}")
            return False
    
    async def subscribe_batch(self, token_ids: List[str]) -> int:
        chunk_size = 100
        success_total = 0
        for i in range(0, len(token_ids), chunk_size):
            chunk = token_ids[i:i + chunk_size]
            if await self.subscribe(chunk): success_total += len(chunk)
            await asyncio.sleep(0.1)
        return success_total

    async def receive_data(self, callback: Callable) -> None:
        if not self.ws: return
        try:
            async for message in self.ws:
                if message == "PONG": continue
                data = json.loads(message)
                messages = data if isinstance(data, list) else [data]
                for msg in messages:
                    if "price_changes" in msg:
                        for change in msg["price_changes"]:
                            token_id, price_val = change.get("asset_id"), change.get("best_bid") or change.get("price")
                            if token_id and price_val:
                                self.prices[token_id] = float(price_val)
                                await callback(token_id, float(price_val))
        except Exception as e:
            logger.error(f"WS error: {e}")