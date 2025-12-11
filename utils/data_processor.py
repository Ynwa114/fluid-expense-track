"""
Combine and normalize EVM + Solana expense data
"""
import pandas as pd
from fetchers.dune_fetcher import fetch_dune_monthly_expenses
from fetchers.solana_fetcher import aggregate_monthly_expenses
from fetchers.price_fetcher import get_fluid_price


def normalize_evm_data(dune_df, fluid_price):
    """
    Normalize EVM data from Dune
    Input: DataFrame with [month, chain, total_claims, total_fluid_claimed, source]
    Output: Standardized DataFrame
    """
    if dune_df.empty:
        return pd.DataFrame()
    
    df = dune_df.copy()
    
    # Calculate USD value
    df['usd_value'] = df['total_fluid_claimed'] * fluid_price
    
    # Rename columns to standard schema
    df = df.rename(columns={
        'total_fluid_claimed': 'token_amount',
        'total_claims': 'num_transactions'
    })
    
    # Add token column (all EVM rewards are FLUID)
    df['token'] = 'FLUID'
    
    # Select and order columns
    df = df[['month', 'chain', 'source', 'token', 'token_amount', 'usd_value', 'num_transactions']]
    
    return df


def normalize_solana_data(solana_df, fluid_price):
    """
    Normalize Solana data from Solscan
    Input: DataFrame with [month, token, total_amount, total_usd, num_transactions, chain, source]
    Output: Standardized DataFrame
    """
    if solana_df.empty:
        return pd.DataFrame()
    
    df = solana_df.copy()
    
    # Recalculate USD values with current FLUID price
    # For FLUID, SOL, WSOL tokens
    def calc_usd_value(row):
        if row['token'] in ['FLUID', 'SOL', 'WSOL']:
            return row['total_amount'] * fluid_price
        else:
            # For stablecoins (USDS, USDG, etc.) - already in USD
            return row['total_usd']
    
    df['usd_value'] = df.apply(calc_usd_value, axis=1)
    
    # Rename columns to standard schema
    df = df.rename(columns={
        'total_amount': 'token_amount'
    })
    
    # Select and order columns
    df = df[['month', 'chain', 'source', 'token', 'token_amount', 'usd_value', 'num_transactions']]
    
    return df


def combine_all_expenses(progress_callback=None):
    """
    Fetch and combine all expense data from EVM + Solana
    Returns: (DataFrame, fluid_price, success, error_message)
    """
    try:
        # Get FLUID price first
        if progress_callback:
            progress_callback("💰 Fetching FLUID price...")
        
        fluid_price = get_fluid_price()
        
        if progress_callback:
            progress_callback(f"💵 FLUID Price: ${fluid_price:.4f}")
        
        # Fetch EVM data
        if progress_callback:
            progress_callback("🔗 Fetching EVM expenses...")
        
        evm_df, evm_success, evm_error = fetch_dune_monthly_expenses(progress_callback)
        
        if not evm_success:
            return pd.DataFrame(), fluid_price, False, f"EVM fetch failed: {evm_error}"
        
        # Fetch Solana data
        if progress_callback:
            progress_callback("☀️ Fetching Solana expenses...")
        
        solana_df, sol_success, sol_error = aggregate_monthly_expenses(progress_callback)
        
        if not sol_success:
            return pd.DataFrame(), fluid_price, False, f"Solana fetch failed: {sol_error}"
        
        # Normalize both datasets
        if progress_callback:
            progress_callback("🔄 Normalizing data...")
        
        evm_normalized = normalize_evm_data(evm_df, fluid_price)
        solana_normalized = normalize_solana_data(solana_df, fluid_price)
        
        # Combine
        combined = pd.concat([evm_normalized, solana_normalized], ignore_index=True)
        
        # Sort by month descending
        combined = combined.sort_values('month', ascending=False)
        
        if progress_callback:
            progress_callback(f"✅ Combined {len(combined)} total expense records")
        
        return combined, fluid_price, True, None
        
    except Exception as e:
        error_msg = str(e)
        if progress_callback:
            progress_callback(f"❌ Error combining data: {error_msg}")
        return pd.DataFrame(), 0.30, False, error_msg


def get_summary_metrics(combined_df):
    """
    Calculate summary metrics from combined data
    Returns: dict with metrics
    """
    if combined_df.empty:
        return {
            'total_usd': 0,
            'current_month_usd': 0,
            'evm_total_usd': 0,
            'solana_total_usd': 0,
            'total_transactions': 0
        }
    
    # Current month (most recent month in data)
    current_month = combined_df['month'].max()
    current_month_data = combined_df[combined_df['month'] == current_month]
    
    return {
        'total_usd': combined_df['usd_value'].sum(),
        'current_month_usd': current_month_data['usd_value'].sum(),
        'evm_total_usd': combined_df[combined_df['source'] == 'EVM']['usd_value'].sum(),
        'solana_total_usd': combined_df[combined_df['source'] == 'Solana']['usd_value'].sum(),
        'total_transactions': combined_df['num_transactions'].sum(),
        'current_month': current_month
    }


if __name__ == "__main__":
    print("Testing data processor...")
    
    def print_progress(msg):
        print(msg)
    
    df, fluid_price, success, error = combine_all_expenses(print_progress)
    
    if success:
        print(f"\n✅ Success!")
        print(f"\nCombined data shape: {df.shape}")
        print(f"\nFirst few rows:")
        print(df.head(10))
        
        print(f"\nSummary by chain:")
        print(df.groupby('chain')['usd_value'].sum().sort_values(ascending=False))
        
        print(f"\nSummary by source:")
        print(df.groupby('source')['usd_value'].sum())
        
        metrics = get_summary_metrics(df)
        print(f"\nOverall metrics:")
        for key, value in metrics.items():
            if 'usd' in key:
                print(f"  {key}: ${value:,.2f}")
            else:
                print(f"  {key}: {value}")
    else:
        print(f"\n❌ Error: {error}")
