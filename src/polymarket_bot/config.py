# config.py
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent / "config" / ".env"
if not env_path.exists():
    # Fallback to root
    env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# API Configuration
API_KEY = os.getenv("POLYMARKET_API_KEY")
API_SECRET = os.getenv("POLYMARKET_API_SECRET")
API_PASSPHRASE = os.getenv("POLYMARKET_API_PASSPHRASE")
PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")

# Validate required credentials - FAIL HARD if missing
required_env_vars = ["POLYMARKET_API_KEY", "POLYMARKET_API_SECRET", 
                     "POLYMARKET_API_PASSPHRASE", "POLYMARKET_PRIVATE_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    error_msg = f"CRITICAL: Missing required environment variables: {', '.join(missing_vars)}"
    logging.error(error_msg)
    raise EnvironmentError(error_msg)

# API URLs
GAMMA_API_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"
CLOB_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Blockchain Configuration
CHAIN_ID = 137  # Polygon (MATIC)

# Trading Configuration
PROFIT_THRESHOLD = 0.02  # 2% minimum profit threshold
MAX_USDC_ALLOCATION = 0.05  # Max 5% of balance per trade
SLIPPAGE_TOLERANCE = 0.01  # Max 1% slippage tolerance
MIN_LIQUIDITY = 100  # Minimum $100 liquidity at target price
STOP_LOSS_PERCENT = 0.05  # 5% stop loss on failed leg
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
WS_PING_INTERVAL = 20
WS_PING_TIMEOUT = 20
API_RATE_LIMIT_DELAY = 1  # seconds between API calls
MARKET_SCAN_INTERVAL = 3600  # 1 hour in seconds
ORDER_TIMEOUT = 30  # seconds to wait for order confirmation

# Logging Configuration
log_file = Path(__file__).parent.parent.parent / "logs" / "polymarket_bot.log"
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_file), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)