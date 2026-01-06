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
        try:
            self.ws = await websockets.connect(CLOB_WS_URL)
            print("Connected to CLOB WebSocket.")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def subscribe(self, clob_token_id):
        payload = {
            "type": "subscribe",
            "channels": ["order_book"],
            "assets_ids": [clob_token_id]
        }
        await self.ws.send(json.dumps(payload))
        print(f"Subscribed to updates for: {clob_token_id}")

    async def receive_data(self, callback):
        try:
            async for message in self.ws:
                data = json.loads(message)
                
                # בדיקת הודעות ספר פקודות
                if "bids" in data and len(data["bids"]) > 0:
                    token_id = data.get("asset_id")
                    price = float(data["bids"][0][0])
                    self.prices[token_id] = price
                    await callback(token_id, price)
                
                # הודעת דופק מהשרת (כדי לדעת שהחיבור חי)
                elif data.get("type") == "pong":
                    pass 
        except Exception as e:
            print(f"WS Error: {e}")