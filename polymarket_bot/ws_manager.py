# ws_manager.py
import asyncio
import websockets
import json
from config import CLOB_WS_URL

class WebSocketManager:
    def __init__(self):
        self.ws = None
        self.prices = {}

    async def connect(self):
        """מתחבר לשרת ה-WebSocket של פולימרקט"""
        try:
            self.ws = await websockets.connect(CLOB_WS_URL)
            print("Connected to CLOB WebSocket.")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def subscribe(self, clob_token_id):
        """נרשם לעדכוני מחיר עבור טוקן בודד"""
        if self.ws:
            payload = {
                "type": "subscribe",
                "channels": ["order_book"],
                "assets_ids": [clob_token_id]
            }
            await self.ws.send(json.dumps(payload))
            print(f"Subscribed to: {clob_token_id}")

    async def receive_data(self, callback):
        """מאזין לנתונים ומפעיל את פונקציית הטיפול"""
        if not self.ws:
            return

        try:
            async for message in self.ws:
                if not message:
                    continue
                
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue
                
                # טיפול ברשימת הודעות או הודעה בודדת
                messages = data if isinstance(data, list) else [data]
                
                for msg in messages:
                    if isinstance(msg, dict) and "bids" in msg and len(msg["bids"]) > 0:
                        token_id = msg.get("asset_id")
                        price = float(msg["bids"][0][0])
                        self.prices[token_id] = price
                        await callback(token_id, price)
        except Exception as e:
            print(f"WS Error: {e}")