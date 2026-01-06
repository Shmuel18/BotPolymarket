# main.py
import asyncio
from scanner import scan_polymarket_for_hierarchical_markets
from ws_manager import WebSocketManager
from logic import check_arbitrage
from executor import OrderExecutor

current_prices = {}
active_pairs = []
executor = OrderExecutor()

async def price_update_handler(token_id, price):
    global current_prices
    current_prices[token_id] = price
    # הדפסה שקטה כדי לא להציף את המסך
    # print(f"Price Update: {token_id} -> {price}")

    # בדיקת ארביטראז'
    opportunities = check_arbitrage(active_pairs, current_prices)
    for opp in opportunities:
        print(f"💰 הזדמנות רווח! {opp['event']} | רווח: {opp['profit']:.4f}")
        # await executor.execute_trade(opp['buy_token'], 'buy', 10, price)

async def main():
    global active_pairs
    ws = WebSocketManager()
    
    while True:
        print("🔍 מחפש שווקים היררכיים...")
        markets = scan_polymarket_for_hierarchical_markets()
        
        if markets:
            active_pairs = []
            for title, data in markets.items():
                ids = data["clob_token_ids"]
                for i in range(len(ids) - 1):
                    active_pairs.append({
                        'event_title': title,
                        'parent_id': ids[i],
                        'child_id': ids[i+1]
                    })
            
            print(f"✅ נמצאו {len(active_pairs)} זוגות לניטור.")
            
            if await ws.connect():
                for pair in active_pairs:
                    await ws.subscribe(pair['parent_id'])
                    await ws.subscribe(pair['child_id'])
                
                print("--- ניטור פעיל והתחלת חיפוש ארביטראז' ---")
                await ws.receive_data(price_update_handler)
                break
        
        print("מנסה שוב בעוד 60 שניות...")
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
    