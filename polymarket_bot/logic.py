# logic.py
from config import PROFIT_THRESHOLD

def check_arbitrage(pairs, current_prices):
    """
    בודק את כל הזוגות שנסרקו ומחפש פערי מחירים לא הגיוניים.
    לוגיקה: אם מחיר 'YES' של תנאי קשה (105K) גבוה ממחיר 'YES' של תנאי קל (100K).
    """
    opportunities = []

    for pair in pairs:
        low_id = pair['parent_id']  # למשל 100K
        high_id = pair['child_id'] # למשל 105K
        
        price_low = current_prices.get(low_id)
        price_high = current_prices.get(high_id)

        if price_low and price_high:
            # אם התנאי הקשה יקר יותר מהקל + מרווח רווח
            if price_high > (price_low + PROFIT_THRESHOLD):
                diff = price_high - price_low
                opportunities.append({
                    'buy_token': low_id,
                    'sell_token': high_id,
                    'profit': diff,
                    'event': pair['event_title']
                })
    
    return opportunities