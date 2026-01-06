# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# מפתחות API - לפי השמות ב-.env שלך
API_KEY = os.getenv("POLYMARKET_API_KEY")
API_SECRET = os.getenv("POLYMARKET_API_SECRET")
API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY") 

# כתובות שרתים
GAMMA_API_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"

# הכתובת הנכונה ל-WebSocket (ללא /market בסוף)
CLOB_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/" 

CHAIN_ID = 137

# הגדרות מסחר
PROFIT_THRESHOLD = 0.02
MAX_USDC_ALLOCATION = 0.05