# Fluid Protocol - Unified Expense Tracker

Real-time tracking of FLUID reward expenses across all chains (Ethereum, Base, Arbitrum, Plasma, Solana).

## Features

- ✅ **EVM Expenses** - Fetched from Dune Analytics (Ethereum, Base, Arbitrum, Plasma)
- ✅ **Solana Expenses** - Fetched from Solscan API (treasury outflows)
- ✅ **Real-time FLUID Price** - From Fluid API
- ✅ **Monthly Aggregation** - Time series analysis
- ✅ **Chain Breakdown** - See expenses per chain
- ✅ **Smart Filtering** - Excludes partner-sponsored rewards (Maple USDC)
- ✅ **Caching** - Reduces API calls

## Architecture

```
unified-expense-tracker/
├── .env                          # API keys (DO NOT COMMIT)
├── .gitignore
├── requirements.txt
├── unified_expense_tracker.py    # Main Streamlit dashboard
├── fetchers/
│   ├── __init__.py
│   ├── dune_fetcher.py          # Fetch EVM data from Dune
│   ├── solana_fetcher.py        # Fetch Solana data from Solscan
│   └── price_fetcher.py         # Get FLUID price
├── utils/
│   ├── __init__.py
│   └── data_processor.py        # Combine & normalize data
└── cache/                        # Auto-generated cache files
    ├── dune_cache.json
    └── solana_cache.json
```

## Setup

### 1. Install Dependencies

```bash
cd unified-expense-tracker
pip install -r requirements.txt
```

### 2. Configure Environment Variables

The `.env` file is already configured with your API keys:
- Dune API Key: `TZ2g34RKRrq8pbjYHXaywKLL02XcTZQu`
- Solscan API Key: `eyJhbGc...` (full JWT token)
- Dune Query ID: `6339248` (monthly expenses query)

### 3. Run Dashboard

```bash
streamlit run unified_expense_tracker.py
```

The dashboard will open at `http://localhost:8501`

## Data Sources

### EVM (Dune)
- **Source**: Dune Query #6339248
- **Chains**: Ethereum, Base, Arbitrum, Plasma
- **Data**: Monthly aggregated FLUID claims from merkle distributors
- **Filters**: Excludes Maple-sponsored USDC rewards

### Solana (Solscan)
- **Source**: Solscan Pro API
- **Treasury**: `Cvnta5ecoiCgNbLEXYm6kvhJMmRv3JM3ksKgTLVPg4hk`
- **Data**: Treasury outflow transactions
- **Filters**: 
  - Only outflows (expenses)
  - Excludes USDC (partner-sponsored)
  - Minimum $1,000 USD value

## How It Works

1. **Fetch FLUID Price** - Current price from Fluid API dexes endpoint
2. **Fetch EVM Data** - Monthly expenses from Dune (already aggregated)
3. **Fetch Solana Data** - Raw transactions from Solscan, then aggregate monthly
4. **Normalize** - Convert both to standard schema with USD values
5. **Combine** - Merge EVM + Solana into single dataset
6. **Visualize** - Display charts, metrics, and tables

## Testing Individual Components

### Test Dune Fetcher
```bash
python fetchers/dune_fetcher.py
```

### Test Solana Fetcher
```bash
python fetchers/solana_fetcher.py
```

### Test Price Fetcher
```bash
python fetchers/price_fetcher.py
```

### Test Data Processor
```bash
python utils/data_processor.py
```

## Caching

- **Dune Cache**: 1 hour TTL
- **Solscan Cache**: Persistent until manually cleared
- **FLUID Price**: 5 minutes in-memory cache

To clear caches, click "🔄 Refresh Data" in the dashboard sidebar.

## Dashboard Features

### Overview Tab
- EVM vs Solana pie chart
- Chain distribution bar chart
- Key metrics

### By Chain Tab
- Monthly stacked bar chart by chain
- Chain summary table

### Time Series Tab
- Total monthly expenses line chart
- EVM vs Solana area chart

### Detailed Data Tab
- Full data table
- CSV export

## Maintenance

### Adding New EVM Distributor
1. Update Dune query to include new contract
2. Refresh dashboard (cache auto-updates)

### Adding New Solana Program
- No changes needed! All treasury outflows are automatically tracked

## Notes

- All FLUID rewards are valued at current FLUID price
- Solana expenses exclude USDC (considered partner-sponsored)
- EVM expenses exclude Maple syrupUSDC rewards (marked in Dune query)
- Cache refreshes automatically after TTL expires

## Support

For issues or questions, contact the Fluid team.
