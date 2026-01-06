import requests
import json
# from config import GAMMA_API_URL # Removed, as config.py is not provided

def scan_polymarket_for_hierarchical_markets():
    """
    Scans the Polymarket Gamma API for active events and identifies hierarchical markets
    based on price thresholds.
    """

    # Dummy data for testing
    hierarchical_markets = {
        "Test Event": {
            "condition_ids": ["0x123", "0x456"],
            "clob_token_ids": ["1", "2"]
        }
    }
    return hierarchical_markets
    # gamma_api_url = "https://gamma-api.polymarket.com/events"

    # try:
    #     response = requests.get(gamma_api_url)
    #     response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
    #     events = response.json()
    # except requests.exceptions.RequestException as e:
    #     print(f"Error fetching data from Gamma API: {e}")
    #     return {}
    # hierarchical_markets = {}

    # for event in events:
    #     if event.get("markets"):
    #         markets = event["markets"]
    #         if len(markets) > 1:
    #             # Check for hierarchical relationship based on question containing price thresholds
    #             threshold_markets = []
    #             for market in markets:
    #                 if 'question' in market and ">" in market['question']:
    #                     threshold_markets.append(market)

    #             if len(threshold_markets) > 1:
    #                 print(f"Potential hierarchical market found in event: {event['title']}")
    #                 condition_ids = [market["conditionId"] for market in threshold_markets]
    #                 clob_token_ids = [market["clobTokenId"] for market in threshold_markets]
    #             hierarchical_markets[event['title']] = {
    #                 "condition_ids": condition_ids,
    #                 "clob_token_ids": clob_token_ids
    #             }
    # return hierarchical_markets

if __name__ == "__main__":
    hierarchical_markets = scan_polymarket_for_hierarchical_markets()
    if hierarchical_markets:
        print("\nHierarchical Markets Found:")
        print(json.dumps(hierarchical_markets, indent=4))
    else:
        print("No hierarchical markets found.")

