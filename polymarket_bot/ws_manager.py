import asyncio
import websockets
import json
from config import CLOB_URL

class WebSocketManager:
    def __init__(self):
        self.ws = None
        self.subscriptions = {}

    async def connect(self):
        self.ws = await websockets.connect(CLOB_URL)
        print("Connected to CLOB WebSocket.")

    async def subscribe(self, clob_token_id):
        if clob_token_id not in self.subscriptions:
            payload = {"type": "subscribe", "channel": "order_book", "clobTokenId": clob_token_id}
            await self.ws.send(json.dumps(payload))
            self.subscriptions[clob_token_id] = True
            print(f"Subscribed to order book for clobTokenId: {clob_token_id}")

    async def unsubscribe(self, clob_token_id):
        if clob_token_id in self.subscriptions:
            payload = {"type": "unsubscribe", "channel": "order_book", "clobTokenId": clob_token_id}
            await self.ws.send(json.dumps(payload))
            del self.subscriptions[clob_token_id]
            print(f"Unsubscribed from order book for clobTokenId: {clob_token_id}")

    async def receive_data(self):
        try:
            async for message in self.ws:
                data = json.loads(message)
                # Process the data here (e.g., update order book, calculate arbitrage)
                print(f"Received data: {data}")
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"WebSocket connection closed: {e}")
        finally:
            print("WebSocket disconnected.")
