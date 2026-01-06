# main.py
import asyncio
import time
from scanner import scan_polymarket_for_hierarchical_markets
from ws_manager import WebSocketManager

async def price_update_handler(token_id, price):
    print(f"מחיר עדכני לטוקן {token_id}: {price} USDC")

async def main():
    ws = WebSocketManager()
    
    while True:
        print("סורק שווקים פוטנציאליים...")
        markets = scan_polymarket_for_hierarchical_markets()
        
        if markets:
            print(f"נמצאו {len(markets)} אירועים רלוונטיים. מתחבר ל-WebSocket...")
            if await ws.connect():
                for event, data in markets.items():
                    for token_id in data["clob_token_ids"]:
                        await ws.subscribe(token_id)
                
                print("--- ניטור מחירים חי התחיל ---")
                await ws.receive_data(price_update_handler)
                break # אם הצלחנו להתחבר ולהאזין, יוצאים מהלולאה של החיפוש
        
        print("לא נמצאו שווקים מתאימים כרגע. מנסה שוב בעוד 60 שניות...")
        await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nהבוט נעצר על ידי המשתמש.")