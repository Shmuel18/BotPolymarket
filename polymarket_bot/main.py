import asyncio
import json
import os

from scanner import scan_polymarket_for_hierarchical_markets
from ws_manager import WebSocketManager
from logic import calculate_arbitrage_opportunity
from executor import OrderExecutor

async def main():
    # 1. Scan for hierarchical markets
    hierarchical_markets = scan_polymarket_for_hierarchical_markets()

    if not hierarchical_markets:
        print("No hierarchical markets found. Exiting.")
        return

    print("Found hierarchical markets:", json.dumps(hierarchical_markets, indent=4))

    # 2. Initialize WebSocket Manager and Order Executor
    ws_manager = WebSocketManager()
    executor = OrderExecutor()

    # 3. Connect to WebSocket
    await ws_manager.connect()

    # 4. Subscribe to order books for all relevant clobTokenIds
    all_clob_token_ids = []
    for event_title, market_data in hierarchical_markets.items():
        all_clob_token_ids.extend(market_data["clob_token_ids"])

    for clob_token_id in all_clob_token_ids:
        await ws_manager.subscribe(clob_token_id)

    # 5. Keep receiving data and check for arbitrage opportunities (Simplified)
    try:
        await ws_manager.receive_data()
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        print("Closing WebSocket connection.")
        #Unsubscribe
        for clob_token_id in all_clob_token_ids:
            await ws_manager.unsubscribe(clob_token_id)


if __name__ == "__main__":
    asyncio.run(main())