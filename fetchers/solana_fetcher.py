"""
Fetch Solana expense data from Solscan API
Processes treasury outflows to calculate monthly expenses
"""
import requests
import pandas as pd
from datetime import datetime
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
SOLSCAN_API_KEY = os.getenv('SOLSCAN_API_KEY')
SOLSCAN_API_URL = "https://pro-api.solscan.io/v2.0/account/transfer"
VAULT_API = "https://api.solana.fluid.io/v1/borrowing/vaults"
TREASURY_ADDRESS = os.getenv('TREASURY_ADDRESS', 'Cvnta5ecoiCgNbLEXYm6kvhJMmRv3JM3ksKgTLVPg4hk')
MIN_VALUE_USD = 1000
CACHE_FILE = "cache/solana_cache.json"

# Team address tags
ADDRESS_TAGS = {
    "5AZYLkiU4SPYDeRMcPbPRPmiz2Ny85jWFeV4xmQsVBNo": "Fluid Team",
    "HUBLSmfDxXxxzgg4KM6Q5onHVwBG5KeKjeA2BnvE5D9r": "Fluid Team",
    "7b1zZUuae2F56e66GqpkKe1Tq1BK2ePRRuGGr8ahe2JB": "JUP Team",
    "FH9bgRZrEGFA1d4859wSBdNnHgtU5ZDqFUPccHDnYQ3p": "Maple",
    "DVBfCpHoAtVgcVLFHyUgXaWg5ZaKU8CkekXu23ZD4iod": "Gauntlet",
    "fr6yQkDmWy6R6pecbUsxXaw6EvRJznZ2HsK5frQgud8": "USDG Team",
    "8sjM83a4u2M8YZYshLGKzYxh1VHFfbgtaytwaoEg4bUJ": "Jito Team",
    "8JmDPG5BFQ6gpUPJV9xBixYJLqTKCSNotkXksTmNsQfj": "Sky Team",
    "62SJTxjWbyaPei1HPW9mFX7KMYCEp7Z9zwiL4hGa8WQv": "LBTC Team",
    "EeQmNqm1RcQnee8LTyx6ccVG9FnR8TezQuw2JXq2LC1T": "Sanctum INF Team",
    "41zCUJsKk6cMB94DDtm99qWmyMZfp4GkAhhuz4xTwePu": "PST Team",
    "JANAjsZKJhtHF9PUF8cwjVp5oQjdcHYiGiFgc8TWQjp2": "Binance Campaign",
    "3ssDYFbTpACkshGeYHMBovxB4aE2G6fbZNeVChi85J1k": "Binance Campaign",
    "7s1da8DduuBFqGra5bJBjpnvL5E9mGzCuMk1Qkh4or2Z": "Liquidity Layer",
}


def get_sol_price():
    """Get SOL price from Fluid API"""
    try:
        response = requests.get(VAULT_API, timeout=10)
        vaults = response.json()
        
        for vault in vaults:
            if vault.get('supplyToken', {}).get('symbol') == 'WSOL':
                price = float(vault['supplyToken']['price'])
                return price
        
        return 150.0  # Fallback price
    except:
        return 150.0


def load_cache():
    """Load from cache if exists"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                transactions = cache_data['transactions']
                
                for tx in transactions:
                    if isinstance(tx['timestamp'], str):
                        tx['timestamp'] = datetime.fromisoformat(tx['timestamp'])
                
                return transactions, cache_data['last_updated']
        except:
            return None, None
    return None, None


def save_cache(transactions):
    """Save to cache"""
    os.makedirs('cache', exist_ok=True)
    
    transactions_serializable = []
    for tx in transactions:
        tx_copy = tx.copy()
        if isinstance(tx_copy['timestamp'], datetime):
            tx_copy['timestamp'] = tx_copy['timestamp'].isoformat()
        transactions_serializable.append(tx_copy)
    
    cache_data = {
        "last_updated": datetime.now().isoformat(),
        "transactions": transactions_serializable
    }
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache_data, f)


def fetch_from_solscan(page=1, page_size=40):
    """Fetch transactions from Solscan API"""
    try:
        if not SOLSCAN_API_KEY:
            return [], {}, False, "SOLSCAN_API_KEY not found"
        
        url = f"{SOLSCAN_API_URL}?address={TREASURY_ADDRESS}&page={page}&page_size={page_size}&sort_by=block_time&sort_order=desc"
        headers = {"token": SOLSCAN_API_KEY}
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        if not result.get('success'):
            return [], {}, False, "API returned success=false"
        
        data = result.get('data', [])
        metadata = result.get('metadata', {})
        
        return data, metadata, True, None
        
    except Exception as e:
        return [], {}, False, str(e)


def process_transactions(raw_data, metadata):
    """Process raw Solscan data into clean format"""
    processed = []
    tokens_meta = metadata.get('tokens', {})
    sol_price = get_sol_price()
    
    for tx in raw_data:
        flow = tx.get('flow', '')
        tx_type = 'Inflow' if flow == 'in' else 'Outflow'
        
        if flow == 'in':
            counterparty = tx.get('from_address', '')
        else:
            counterparty = tx.get('to_address', '')
        
        team = ADDRESS_TAGS.get(counterparty, "Unknown")
        
        token_address = tx.get('token_address', '')
        token_info = tokens_meta.get(token_address, {})
        token_symbol = token_info.get('token_symbol', 'UNKNOWN')
        
        amount_raw = tx.get('amount', 0)
        decimals = tx.get('token_decimals', 6)
        amount = amount_raw / (10 ** decimals)
        
        if token_symbol in ['USDC', 'USDT', 'USDS', 'USDG', 'EURC']:
            value_usd = amount * 1.0
        elif token_symbol in ['SOL', 'WSOL']:
            value_usd = amount * sol_price
        else:
            value_usd = tx.get('value', 0)
        
        if value_usd < MIN_VALUE_USD:
            continue
        
        timestamp = datetime.fromisoformat(tx.get('time', '').replace('Z', '+00:00'))
        
        processed.append({
            'signature': tx.get('trans_id', ''),
            'timestamp': timestamp,
            'type': tx_type,
            'token': token_symbol,
            'amount': amount,
            'value_usd': value_usd,
            'counterparty': counterparty,
            'team': team,
            'block_id': tx.get('block_id', 0)
        })
    
    return processed


def fetch_all_transactions(progress_callback=None, max_pages=5):
    """Main fetch function"""
    try:
        cached, last_updated = load_cache()
        if cached:
            if progress_callback:
                progress_callback(f"📂 Loaded {len(cached)} Solana transactions from cache (Updated: {last_updated})")
            return cached, True, None
        
        if progress_callback:
            progress_callback("🔄 Fetching from Solscan API...")
        
        all_transactions = []
        
        for page in range(1, max_pages + 1):
            if progress_callback:
                progress_callback(f"Fetching page {page}/{max_pages}...")
            
            raw_data, metadata, success, error = fetch_from_solscan(page=page, page_size=40)
            
            if not success:
                return [], False, error
            
            if not raw_data:
                break
            
            processed = process_transactions(raw_data, metadata)
            all_transactions.extend(processed)
        
        if progress_callback:
            progress_callback(f"✅ Fetched {len(all_transactions)} Solana transactions (>${MIN_VALUE_USD} USD)")
        
        save_cache(all_transactions)
        
        return all_transactions, True, None
        
    except Exception as e:
        error_msg = str(e)
        if progress_callback:
            progress_callback(f"❌ Solscan Error: {error_msg}")
        return [], False, error_msg


def aggregate_monthly_expenses(progress_callback=None):
    """
    Aggregate Solana transactions into monthly expenses
    Excludes USDC (partner-sponsored rewards)
    Returns: (DataFrame, success, error_message)
    """
    try:
        transactions, success, error = fetch_all_transactions(progress_callback)
        
        if not success:
            return pd.DataFrame(), False, error
        
        if not transactions:
            return pd.DataFrame(), True, "No transactions found"
        
        df = pd.DataFrame(transactions)
        
        # Filter: Only outflows (expenses)
        df = df[df['type'] == 'Outflow']
        
        # Filter: Exclude USDC (partner-sponsored, not Fluid expense)
        df = df[df['token'] != 'USDC']
        
        if len(df) == 0:
            return pd.DataFrame(), True, "No non-USDC outflows found"
        
        # Add month column
        df['month'] = pd.to_datetime(df['timestamp']).dt.to_period('M').dt.to_timestamp()
        
        # Aggregate by month and token
        monthly = df.groupby(['month', 'token']).agg({
            'amount': 'sum',
            'value_usd': 'sum',
            'signature': 'count'  # number of transactions
        }).reset_index()
        
        monthly.columns = ['month', 'token', 'total_amount', 'total_usd', 'num_transactions']
        
        # Add chain and source columns
        monthly['chain'] = 'solana'
        monthly['source'] = 'Solana'
        
        if progress_callback:
            progress_callback(f"✅ Aggregated {len(monthly)} monthly Solana expense records")
        
        return monthly, True, None
        
    except Exception as e:
        error_msg = str(e)
        if progress_callback:
            progress_callback(f"❌ Aggregation Error: {error_msg}")
        return pd.DataFrame(), False, error_msg


def clear_cache():
    """Clear the cache"""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        return True
    return False


if __name__ == "__main__":
    print("Testing Solana fetcher...")
    
    def print_progress(msg):
        print(msg)
    
    # Test monthly aggregation
    df, success, error = aggregate_monthly_expenses(print_progress)
    
    if success:
        print(f"\n✅ Success! Aggregated {len(df)} monthly records")
        print(f"\nData preview:")
        print(df)
        print(f"\nTotal by token:")
        print(df.groupby('token')['total_usd'].sum())
    else:
        print(f"\n❌ Error: {error}")
