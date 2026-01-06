# scanner.py
import requests
import re
from config import GAMMA_API_URL

def extract_price_threshold(question):
    """מוציא מספרים מכל פורמט (למשל: $100,000, 95k, 105.5)"""
    clean_q = question.replace('$', '').replace(',', '')
    match = re.search(r'(\d+(?:\.\d+)?)\s*k?', clean_q.lower())
    if match:
        val = float(match.group(1))
        if 'k' in clean_q.lower() and val < 1000:
            return val * 1000
        return val
    return None

def scan_polymarket_for_hierarchical_markets():
    url = f"{GAMMA_API_URL}/events?active=true&closed=false&limit=500"
    try:
        response = requests.get(url)
        response.raise_for_status()
        events = response.json()
    except Exception as e:
        print(f"Error fetching from Gamma API: {e}")
        return {}

    hierarchical_markets = {}
    for event in events:
        markets = event.get("markets", [])
        if len(markets) < 2: continue

        threshold_markets = []
        for market in markets:
            q = market.get('question', '')
            if 'above' in q.lower() or '>' in q:
                threshold = extract_price_threshold(q)
                
                # חילוץ מזהה בודד כטקסט בלבד (תמיד לוקחים את הראשון - YES)
                t_id = market.get("clobTokenId")
                if not t_id and market.get("clobTokenIds"):
                    t_ids = market.get("clobTokenIds")
                    if isinstance(t_ids, list) and len(t_ids) > 0:
                        t_id = t_ids[0]

                if threshold and t_id:
                    threshold_markets.append({
                        "threshold": threshold,
                        "clob_token_id": str(t_id), # וידוא שמדובר בטקסט בודד
                        "title": q
                    })

        if len(threshold_markets) > 1:
            threshold_markets.sort(key=lambda x: x['threshold'])
            hierarchical_markets[event['title']] = {
                "clob_token_ids": [m["clob_token_id"] for m in threshold_markets]
            }
            print(f"✅ מצאתי שוק היררכי: {event['title']}")
            
    return hierarchical_markets