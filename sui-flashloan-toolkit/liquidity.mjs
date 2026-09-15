// Reads LIVE flash-loan liquidity from NAVI and DeepBook v3 on Sui mainnet.
// Read-only: no signing, no gas spent, no wallet needed.
//
// Usage: node liquidity.mjs

import { NAVISDKClient } from 'navi-sdk';
import { DeepBookClient, mainnetCoins, mainnetPools } from '@mysten/deepbook-v3';
import { SuiGrpcClient } from '@mysten/sui/grpc';

const fmt = (n) =>
  typeof n === 'number' ? n.toLocaleString('en-US', { maximumFractionDigits: 2 }) : n;

async function naviLiquidity() {
  console.log('\n=== NAVI Protocol — live reserve liquidity (mainnet) ===');
  const client = new NAVISDKClient({ networkType: 'mainnet' });
  const allPools = await client.getPoolInfo();

  const wanted = ['SUI', 'USDC', 'USDT', 'wETH', 'wBTC', 'vSUI'];
  const rows = [];

  for (const key of Object.keys(allPools)) {
    const p = allPools[key];
    if (!wanted.includes(p.symbol)) continue;
    rows.push({
      symbol: p.symbol,
      total_supply: p.total_supply,
      total_borrow: p.total_borrow,
      // This is an INDEXER-DERIVED ESTIMATE of free liquidity, not the exact on-chain
      // figure the contract checks. It's usually close (within ~1-2%) but drifts with
      // live utilization — use test-flashloan.mjs --bisect for the real number.
      available_liquidity_estimate: p.total_supply - p.total_borrow,
      borrow_cap_ceiling: p.borrow_cap_ceiling,
      utilization: p.current_borrow_utilization,
    });
  }

  rows.sort((a, b) => b.available_liquidity_estimate - a.available_liquidity_estimate);
  for (const r of rows) {
    console.log(
      `${r.symbol.padEnd(6)} ~available=${fmt(r.available_liquidity_estimate).padEnd(16)} ` +
        `total_supply=${fmt(r.total_supply).padEnd(16)} total_borrow=${fmt(r.total_borrow).padEnd(14)} ` +
        `utilization=${((r.utilization ?? 0) * 100).toFixed(2)}%`,
    );
  }
  return rows;
}

async function deepbookLiquidity() {
  console.log('\n=== DeepBook v3 — live pool vault balances (mainnet) ===');
  const grpcClient = new SuiGrpcClient({ network: 'mainnet', baseUrl: 'https://fullnode.mainnet.sui.io:443' });
  const client = new DeepBookClient({
    client: grpcClient,
    network: 'mainnet',
    address: '0x0000000000000000000000000000000000000000000000000000000000000000',
    coins: mainnetCoins,
    pools: mainnetPools,
  });

  const poolKeys = ['SUI_USDC', 'USDT_USDC', 'DEEP_SUI', 'WUSDC_USDC', 'DEEP_USDC'];
  const rows = [];

  for (const key of poolKeys) {
    try {
      const vb = await client.vaultBalances(key);
      const pool = mainnetPools[key];
      rows.push({ poolKey: key, baseCoin: pool.baseCoin, quoteCoin: pool.quoteCoin, ...vb });
    } catch (e) {
      rows.push({ poolKey: key, error: e.message });
    }
  }

  for (const r of rows) {
    if (r.error) {
      console.log(`${r.poolKey.padEnd(12)} ERROR: ${r.error}`);
      continue;
    }
    console.log(
      `${r.poolKey.padEnd(12)} base(${r.baseCoin})=${fmt(r.base).padEnd(16)} ` +
        `quote(${r.quoteCoin})=${fmt(r.quote).padEnd(16)} deep=${fmt(r.deep)}`,
    );
  }
  console.log(
    '\nNote: DeepBook has no separate cap — the vault balance printed above IS the exact',
    'flash-loan ceiling for that pool (not an estimate).',
  );
  return rows;
}

const [navi, deepbook] = await Promise.all([naviLiquidity(), deepbookLiquidity()]);

console.log('\n=== Raw JSON ===');
console.log(JSON.stringify({ fetchedAt: new Date().toISOString(), navi, deepbook }, null, 2));
