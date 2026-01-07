"""
Script to generate Polymarket API credentials from your private key.
Run this once to create valid API keys for your account.
"""
from py_clob_client.client import ClobClient
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv('config/.env')

CLOB_URL = "https://clob.polymarket.com"
CHAIN_ID = 137  # Polygon mainnet
PRIVATE_KEY = os.getenv('POLYMARKET_PRIVATE_KEY')
FUNDER_ADDRESS = os.getenv('POLYMARKET_FUNDER_ADDRESS')

def generate_credentials():
    """Generate or retrieve API credentials"""
    print("=" * 60)
    print("🔑 POLYMARKET API CREDENTIAL GENERATOR")
    print("=" * 60)
    print()
    
    if not PRIVATE_KEY:
        print("❌ ERROR: POLYMARKET_PRIVATE_KEY not found in config/.env")
        return
    
    if not FUNDER_ADDRESS:
        print("❌ ERROR: POLYMARKET_FUNDER_ADDRESS not found in config/.env")
        return
    
    try:
        # Initialize client with just the private key (no API creds yet)
        print(f"📡 Connecting to {CLOB_URL}...")
        client = ClobClient(
            host=CLOB_URL,
            key=PRIVATE_KEY,
            chain_id=CHAIN_ID,
            signature_type=1,  # POLY_PROXY for email/Google login accounts
            funder=FUNDER_ADDRESS
        )
        
        signer_address = client.get_address()
        print(f"✅ Connected successfully!")
        print(f"   Signer Address: {signer_address}")
        print(f"   Funder Address: {FUNDER_ADDRESS}")
        print()
        
        # Generate or retrieve API credentials
        print("🔐 Generating API credentials...")
        print("   (This may take a few seconds...)")
        
        creds = client.create_or_derive_api_creds()
        
        print()
        print("=" * 60)
        print("✅ SUCCESS! API Credentials Generated:")
        print("=" * 60)
        print()
        print(f"POLYMARKET_API_KEY={creds.api_key}")
        print(f"POLYMARKET_API_SECRET={creds.api_secret}")
        print(f"POLYMARKET_API_PASSPHRASE={creds.api_passphrase}")
        print()
        print("=" * 60)
        print("📝 NEXT STEPS:")
        print("=" * 60)
        print("1. Copy the above credentials")
        print("2. Update your config/.env file with these new values")
        print("3. Keep your POLYMARKET_PRIVATE_KEY and POLYMARKET_FUNDER_ADDRESS unchanged")
        print("4. Run the bot again: python -m src.polymarket_bot.main")
        print()
        print("⚠️  Keep these credentials SECRET - never share them!")
        print("=" * 60)
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ERROR:")
        print("=" * 60)
        print(f"{e}")
        print()
        print("Common issues:")
        print("• Make sure your PRIVATE_KEY is correct (from your EOA wallet)")
        print("• Make sure your FUNDER_ADDRESS is your Proxy wallet address")
        print("• Check your internet connection")
        print("=" * 60)

if __name__ == "__main__":
    generate_credentials()
