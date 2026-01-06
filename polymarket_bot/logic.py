from config import PROFIT_THRESHOLD

def calculate_arbitrage_opportunity(price_a, price_b, fees, slippage):
    """
    Calculates the potential profit from an arbitrage opportunity.
    """
    profit = (price_b - price_a) - (fees + slippage)
    net_profit = profit / price_a  # Calculate profit percentage

    if net_profit > PROFIT_THRESHOLD:
        return net_profit
    else:
        return None