"""
Configuration file for API credentials and settings.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API keys and endpoints
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
HELIUS_RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

RANGE_API_KEY = os.getenv("RANGE_API_KEY")
RANGE_API_URL = "https://api.range.org/v1"

RUGCHECK_JWT_TOKEN = os.getenv("RUGCHECK_JWT_TOKEN")
RUGCHECK_API_URL = "https://api.rugcheck.xyz/v1"

VYBE_API_KEY = os.getenv("VYBE_API_KEY")
VYBE_API_URL = "https://api.vybe.io/v1"  # This URL might need to be adjusted

# Network configuration
SOLANA_NETWORK = "mainnet"  # Options: mainnet, devnet, testnet

# Data storage configuration
DATA_DIR = os.getenv("DATA_DIR", "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

# Create directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# Rate limiting configuration
RATE_LIMIT = {
    "helius": 5,     # requests per second
    "range": 2,      # requests per second
    "rugcheck": 2,   # requests per second
    "vybe": 3        # requests per second
}

# Timeouts
REQUEST_TIMEOUT = 30  # seconds

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(DATA_DIR, "collection.log")