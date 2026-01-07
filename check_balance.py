"""
Check USDC balance and allowance for trading on Polymarket
"""
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds
from dotenv import load_dotenv
import os

load_dotenv('config/.env')

CLOB_URL = "https://clob.polymarket.com"
CHAIN_ID = 137
PRIVATE_KEY = os.getenv('POLYMARKET_PRIVATE_KEY')
FUNDER_ADDRESS = os.getenv('POLYMARKET_FUNDER_ADDRESS')
API_KEY = os.getenv('POLYMARKET_API_KEY')
API_SECRET = os.getenv('POLYMARKET_API_SECRET')
API_PASSPHRASE = os.getenv('POLYMARKET_API_PASSPHRASE')

def check_balance():
    """Check balance and allowance"""
    print("=" * 60)
    print("💰 POLYMARKET BALANCE CHECKER")
    print("=" * 60)
    print()
    
    try:
        creds = ApiCreds(
            api_key=API_KEY,
            api_secret=API_SECRET,
            api_passphrase=API_PASSPHRASE
        )
        
        client = ClobClient(
            host=CLOB_URL,
            key=PRIVATE_KEY,
            chain_id=CHAIN_ID,
            creds=creds,
            signature_type=1,
            funder=FUNDER_ADDRESS
        )
        
        print(f"📍 Funder Address: {FUNDER_ADDRESS}")
        print()
        
        # Check balances
        print("🔍 Checking balances...")
        
        # Get balance from API
        try:
            # Try to get balance info
            balance_info = client.get_balance_allowance()
            print(f"✅ USDC Balance: ${balance_info.get('balance', 'N/A')}")
            print(f"✅ USDC Allowance: ${balance_info.get('allowance', 'N/A')}")
        except Exception as e:
            print(f"⚠️  Could not fetch balance: {e}")
            print()
            print("📝 Manual check options:")
            print(f"   1. Visit: https://polygonscan.com/address/{FUNDER_ADDRESS}")
            print(f"   2. Check USDC balance on Polymarket.com")
        
        print()
        print("=" * 60)
        print("📝 WHAT YOU NEED:")
        print("=" * 60)
        print("1. USDC tokens in your Funder wallet")
        print("2. Approved allowance for CTF Exchange contract")
        print()
        print("💡 To add funds:")
        print("   • Go to https://polymarket.com")
        print("   • Click 'Deposit' and add USDC")
        print()
        print("💡 To set allowance:")
        print("   • Making any trade on Polymarket.com will set it automatically")
        print("   • Or use the approve_allowance.py script")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_balance()
