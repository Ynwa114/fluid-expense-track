"""
Fetch EVM expense data from Dune API
"""
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from dune_client.client import DuneClient

load_dotenv()

DUNE_API_KEY = os.getenv('DUNE_API_KEY')
DUNE_MONTHLY_QUERY_ID = int(os.getenv('DUNE_MONTHLY_QUERY_ID', '6339248'))
CACHE_FILE = "cache/dune_cache.json"
CACHE_TTL_MINUTES = 60


def fetch_dune_monthly_expenses(progress_callback=None):
    """
    Fetch monthly EVM expenses from Dune
    Returns: (DataFrame, success, error_message)
    """
    try:
        # Check cache first
        cached_df, last_updated = load_cache()
        if cached_df is not None:
            if progress_callback:
                progress_callback(f"📂 Loaded Dune data from cache (Updated: {last_updated})")
            return cached_df, True, None
        
        if progress_callback:
            progress_callback("🔄 Fetching from Dune API...")
        
        if not DUNE_API_KEY:
            return pd.DataFrame(), False, "DUNE_API_KEY not found in environment"
        
        # Initialize Dune client
        dune = DuneClient(DUNE_API_KEY)
        
        # Get latest query result
        query_result = dune.get_latest_result(DUNE_MONTHLY_QUERY_ID)
        
        # Extract rows
        rows = query_result.result.rows
        
        if not rows:
            return pd.DataFrame(), False, "No data returned from Dune"
        
        # Convert to DataFrame
        df = pd.DataFrame([dict(row) for row in rows])
        
        # Parse month column and remove timezone info
        df['month'] = pd.to_datetime(df['month']).dt.tz_localize(None)
        
        # Ensure numeric types
        df['total_claims'] = df['total_claims'].astype(int)
        df['total_fluid_claimed'] = df['total_fluid_claimed'].astype(float)
        
        # Add source column
        df['source'] = 'EVM'
        
        if progress_callback:
            progress_callback(f"✅ Fetched {len(df)} monthly records from Dune")
        
        # Save to cache
        save_cache(df)
        
        return df, True, None
        
    except Exception as e:
        error_msg = str(e)
        if progress_callback:
            progress_callback(f"❌ Dune API Error: {error_msg}")
        return pd.DataFrame(), False, error_msg


def load_cache():
    """Load cached Dune data if fresh"""
    if not os.path.exists(CACHE_FILE):
        return None, None
    
    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        
        last_updated = datetime.fromisoformat(cache['last_updated'])
        age_minutes = (datetime.now() - last_updated).total_seconds() / 60
        
        if age_minutes < CACHE_TTL_MINUTES:
            df = pd.DataFrame(cache['data'])
            df['month'] = pd.to_datetime(df['month']).dt.tz_localize(None)
            return df, cache['last_updated']
        
        return None, None
    except:
        return None, None


def save_cache(df):
    """Save DataFrame to cache"""
    os.makedirs('cache', exist_ok=True)
    
    # Convert datetime to string for JSON
    df_copy = df.copy()
    df_copy['month'] = df_copy['month'].astype(str)
    
    cache = {
        'last_updated': datetime.now().isoformat(),
        'data': df_copy.to_dict('records')
    }
    
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)


def clear_cache():
    """Clear Dune cache"""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        return True
    return False


if __name__ == "__main__":
    # Test the module
    print("Testing Dune fetcher...")
    
    def print_progress(msg):
        print(msg)
    
    df, success, error = fetch_dune_monthly_expenses(print_progress)
    
    if success:
        print(f"\n✅ Success! Fetched {len(df)} records")
        print(f"\nData preview:")
        print(df.head())
        print(f"\nSummary:")
        print(df.groupby('chain')['total_fluid_claimed'].sum())
    else:
        print(f"\n❌ Error: {error}")