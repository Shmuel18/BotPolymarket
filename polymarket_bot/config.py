# config.py
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("POLYMARKET_API_KEY")
API_SECRET = os.getenv("POLYMARKET_API_SECRET")
API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")

GAMMA_API_URL = "https://gamma-api.polymarket.com/events"
CLOB_URL = "wss://clob.polymarket.com"

PROFIT_THRESHOLD = 0.02  # 2% profit threshold
MAX_USDC_ALLOCATION = 0.05  # 5% of total USDC balance per trade
