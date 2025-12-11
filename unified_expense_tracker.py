"""
Unified Expense Tracker Dashboard
Combines EVM (Dune) + Solana (Solscan) reward expenses
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.data_processor import combine_all_expenses, get_summary_metrics
from fetchers.dune_fetcher import clear_cache as clear_dune_cache
from fetchers.solana_fetcher import clear_cache as clear_solana_cache

# Page config
st.set_page_config(
    page_title="Fluid Protocol - Expense Tracker",
    page_icon="💰",
    layout="wide"
)

# Title
st.title("💰 Fluid Protocol - Unified Expense Tracker")
st.markdown("### Real-time tracking of FLUID reward expenses across all chains")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        clear_dune_cache()
        clear_solana_cache()
        st.rerun()
    
    st.markdown("---")
    st.markdown("**Data Sources:**")
    st.markdown("- 🔗 EVM: Dune Analytics")
    st.markdown("- ☀️ Solana: Solscan API")
    st.markdown("- 💵 Price: Fluid API")

# Load data
progress_container = st.empty()

def show_progress(msg):
    progress_container.info(msg)

with st.spinner("Loading data..."):
    combined_df, fluid_price, success, error = combine_all_expenses(show_progress)
    progress_container.empty()

if not success:
    st.error(f"❌ Error loading data: {error}")
    st.stop()

if combined_df.empty:
    st.warning("⚠️ No expense data found")
    st.stop()

# Calculate metrics
metrics = get_summary_metrics(combined_df)

# Display metrics
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Total Spent (All Time)",
        f"${metrics['total_usd']:,.0f}",
        help="Total USD value of all reward expenses"
    )

with col2:
    st.metric(
        "This Month",
        f"${metrics['current_month_usd']:,.0f}",
        help=f"Total for {metrics['current_month'].strftime('%B %Y')}"
    )

with col3:
    st.metric(
        "EVM Total",
        f"${metrics['evm_total_usd']:,.0f}",
        help="Ethereum + Base + Arbitrum + Plasma"
    )

with col4:
    st.metric(
        "Solana Total",
        f"${metrics['solana_total_usd']:,.0f}",
        help="Solana chain expenses (excluding USDC)"
    )

with col5:
    st.metric(
        "FLUID Price",
        f"${fluid_price:.4f}",
        help="Current FLUID token price"
    )

st.markdown("---")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Overview", 
    "🔗 By Chain", 
    "📅 Time Series",
    "📋 Detailed Data"
])

# Tab 1: Overview
with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("EVM vs Solana")
        
        source_summary = combined_df.groupby('source')['usd_value'].sum().reset_index()
        
        fig_source = px.pie(
            source_summary,
            values='usd_value',
            names='source',
            title='Expense Distribution by Source',
            hole=0.4,
            color_discrete_sequence=['#3b82f6', '#a855f7']
        )
        fig_source.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_source, use_container_width=True)
        
        # Show totals
        for _, row in source_summary.iterrows():
            st.metric(
                f"{row['source']} Total",
                f"${row['usd_value']:,.0f}"
            )
    
    with col2:
        st.subheader("By Chain")
        
        chain_summary = combined_df.groupby('chain')['usd_value'].sum().reset_index()
        chain_summary = chain_summary.sort_values('usd_value', ascending=False)
        
        fig_chain = px.bar(
            chain_summary,
            x='chain',
            y='usd_value',
            title='Total Expenses by Chain',
            color='chain',
            labels={'usd_value': 'USD Value', 'chain': 'Chain'}
        )
        fig_chain.update_layout(showlegend=False)
        st.plotly_chart(fig_chain, use_container_width=True)
        
        # Show chain breakdown
        for _, row in chain_summary.iterrows():
            pct = (row['usd_value'] / metrics['total_usd']) * 100
            st.metric(
                row['chain'].title(),
                f"${row['usd_value']:,.0f}",
                f"{pct:.1f}% of total"
            )

# Tab 2: By Chain
with tab2:
    st.subheader("Monthly Expenses by Chain")
    
    monthly_by_chain = combined_df.groupby(['month', 'chain'])['usd_value'].sum().reset_index()
    
    fig_monthly_chain = px.bar(
        monthly_by_chain,
        x='month',
        y='usd_value',
        color='chain',
        title='Monthly Reward Expenses (Stacked by Chain)',
        labels={'usd_value': 'USD Value', 'month': 'Month'},
        barmode='stack'
    )
    
    st.plotly_chart(fig_monthly_chain, use_container_width=True)
    
    # Summary table
    st.subheader("Chain Summary Table")
    
    chain_table = combined_df.groupby('chain').agg({
        'usd_value': 'sum',
        'token_amount': 'sum',
        'num_transactions': 'sum'
    }).reset_index()
    
    chain_table.columns = ['Chain', 'Total USD', 'Total Tokens', 'Total Transactions']
    chain_table['Total USD'] = chain_table['Total USD'].apply(lambda x: f"${x:,.2f}")
    chain_table['Total Tokens'] = chain_table['Total Tokens'].apply(lambda x: f"{x:,.2f}")
    
    st.dataframe(chain_table, use_container_width=True)

# Tab 3: Time Series
with tab3:
    st.subheader("Time Series Analysis")
    
    # Monthly total
    monthly_total = combined_df.groupby('month')['usd_value'].sum().reset_index()
    
    fig_timeline = px.line(
        monthly_total,
        x='month',
        y='usd_value',
        title='Total Monthly Expenses (All Chains)',
        labels={'usd_value': 'USD Value', 'month': 'Month'},
        markers=True
    )
    
    st.plotly_chart(fig_timeline, use_container_width=True)
    
    # EVM vs Solana over time
    st.subheader("EVM vs Solana Over Time")
    
    monthly_by_source = combined_df.groupby(['month', 'source'])['usd_value'].sum().reset_index()
    
    fig_source_time = px.area(
        monthly_by_source,
        x='month',
        y='usd_value',
        color='source',
        title='Monthly Expenses by Source',
        labels={'usd_value': 'USD Value', 'month': 'Month'}
    )
    
    st.plotly_chart(fig_source_time, use_container_width=True)

# Tab 4: Detailed Data
with tab4:
    st.subheader("Detailed Expense Data")
    
    # Format for display
    display_df = combined_df.copy()
    display_df['month'] = display_df['month'].dt.strftime('%Y-%m')
    display_df['usd_value'] = display_df['usd_value'].apply(lambda x: f"${x:,.2f}")
    display_df['token_amount'] = display_df['token_amount'].apply(lambda x: f"{x:,.2f}")
    
    st.dataframe(
        display_df,
        use_container_width=True,
        column_config={
            "month": "Month",
            "chain": "Chain",
            "source": "Source",
            "token": "Token",
            "token_amount": "Amount",
            "usd_value": "USD Value",
            "num_transactions": "# Transactions"
        }
    )
    
    # Export button
    csv = combined_df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"fluid_expenses_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )

# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
