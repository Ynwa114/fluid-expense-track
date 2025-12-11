"""
Fetch FLUID token price from Fluid API
"""
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

FLUID_API_URL = os.getenv('FLUID_API_URL', 'https://api.fluid.instadapp.io')
DEXES_ENDPOINT = f"{FLUID_API_URL}/1/dexes"

# In-memory cache
_price_cache = {
    'price': None,
    'timestamp': None
}
CACHE_TTL_MINUTES = 5


def get_fluid_price(use_cache=True):
    """
    Get current FLUID token price in USD
    Returns: float (price) or None on error
    """
    # Check cache
    if use_cache and _price_cache['timestamp']:
        age = (datetime.now() - _price_cache['timestamp']).total_seconds() / 60
        if age < CACHE_TTL_MINUTES:
            return _price_cache['price']
    
    try:
        response = requests.get(DEXES_ENDPOINT, timeout=10)
        response.raise_for_status()
        
        dexes = response.json()
        
        # Find FLUID token in any dex listing
        for dex in dexes:
            # Check token0
            if 'token0' in dex and dex['token0'].get('symbol') == 'FLUID':
                price = float(dex['token0']['price'])
                
                # Update cache
                _price_cache['price'] = price
                _price_cache['timestamp'] = datetime.now()
                
                return price
            
            # Check token1
            if 'token1' in dex and dex['token1'].get('symbol') == 'FLUID':
                price = float(dex['token1']['price'])
                
                # Update cache
                _price_cache['price'] = price
                _price_cache['timestamp'] = datetime.now()
                
                return price
        
        # Fallback price if not found
        return 0.30
        
    except Exception as e:
        print(f"Error fetching FLUID price: {e}")
        # Return cached price if available, otherwise fallback
        if _price_cache['price']:
            return _price_cache['price']
        return 0.30


def clear_price_cache():
    """Clear the price cache"""
    _price_cache['price'] = None
    _price_cache['timestamp'] = None


if __name__ == "__main__":
    print("Testing FLUID price fetcher...")
    price = get_fluid_price()
    print(f"Current FLUID price: ${price:.4f}")
