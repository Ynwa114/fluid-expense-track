// Dry-runs a REAL borrow+repay flash-loan transaction against NAVI or DeepBook v3
// on Sui mainnet, via Sui's public simulateTransaction RPC.
//
// This is 100% read-only: nothing is signed, nothing is broadcast, no wallet or
// gas is spent, no real funds move. It builds the exact transaction a real flash
// loan would use and asks the chain "would this succeed against current state?"
//
// Usage:
//   node test-flashloan.mjs navi <SYMBOL> <amount>
//   node test-flashloan.mjs navi <SYMBOL> --bisect
//   node test-flashloan.mjs deepbook <POOL_KEY> <amount> [--side=base|quote]
//   node test-flashloan.mjs deepbook <POOL_KEY> --bisect [--side=base|quote]
//
// Examples:
//   node test-flashloan.mjs navi USDC 5000000
//   node test-flashloan.mjs navi USDC --bisect
//   node test-flashloan.mjs deepbook SUI_USDC 300000 --side=quote
//   node test-flashloan.mjs deepbook SUI_USDC --bisect --side=quote
//
// NAVI <SYMBOL> options: Sui, USDT, WETH, vSui, WBTC, nUSDC (native USDC — this is
// what shows up simply as "USDC" in NAVI's UI/API), wUSDC (Wormhole USDC), and others
// — run `node -e "import('navi-sdk').then(({pool})=>console.log(Object.keys(pool)))"`
// for the full list.
//
// DeepBook <POOL_KEY> options: SUI_USDC, USDT_USDC, DEEP_SUI, DEEP_USDC, WUSDC_USDC,
// etc — see mainnetPools in @mysten/deepbook-v3.

import { flashloan, repayFlashLoan, pool as naviPool } from 'navi-sdk';
import { DeepBookClient, mainnetCoins, mainnetPools } from '@mysten/deepbook-v3';
import { SuiGrpcClient } from '@mysten/sui/grpc';
import { Transaction } from '@mysten/sui/transactions';

const DUMMY_SENDER = '0x0000000000000000000000000000000000000000000000000000000000000001';
const grpcClient = new SuiGrpcClient({ network: 'mainnet', baseUrl: 'https://fullnode.mainnet.sui.io:443' });

async function simulate(tx) {
  tx.setSender(DUMMY_SENDER);
  tx.setGasBudget(1_000_000_000);
  const res = await grpcClient.core.simulateTransaction({
    transaction: tx,
    include: { commandResults: true, effects: true },
  });
  // Successful sims come back as { $kind: 'Transaction', ... } with NO status field.
  // Only failures carry { $kind: 'FailedTransaction', FailedTransaction: { status } }.
  const isFailure = res.$kind === 'FailedTransaction';
  const error = isFailure ? res.FailedTransaction.status?.error?.message ?? null : null;
  return { success: !isFailure, error };
}

function buildNaviTx(symbol, amount) {
  const cfg = naviPool[symbol];
  if (!cfg) throw new Error(`Unknown NAVI symbol "${symbol}". Try: ${Object.keys(naviPool).join(', ')}`);

  return async () => {
    const tx = new Transaction();
    const rawAmount = Math.round(amount * 1e6); // NAVI stablecoins are 6 decimals; SUI is 9 — adjust if testing SUI/vSUI/WBTC
    const [balance, receipt] = await flashloan(tx, cfg, rawAmount);
    // Repay with the exact same balance (NAVI flash loans carry no fee in our testing).
    // The leftover Balance<T> from repayFlashLoan has no `drop` ability and MUST be
    // consumed, or the whole transaction fails PTB verification (UnusedValueWithoutDrop)
    // before any Move code even runs — which would hide the real liquidity check.
    const [remainder] = await repayFlashLoan(tx, cfg, receipt, balance);
    const leftoverCoin = tx.moveCall({
      target: '0x2::coin::from_balance',
      arguments: [remainder],
      typeArguments: [cfg.type],
    });
    tx.transferObjects([leftoverCoin], DUMMY_SENDER);
    return tx;
  };
}

function buildDeepBookTx(poolKey, amount, side) {
  if (!mainnetPools[poolKey]) {
    throw new Error(`Unknown DeepBook pool "${poolKey}". Try: ${Object.keys(mainnetPools).join(', ')}`);
  }

  return async () => {
    const client = new DeepBookClient({
      client: grpcClient,
      network: 'mainnet',
      address: DUMMY_SENDER,
      coins: mainnetCoins,
      pools: mainnetPools,
    });
    const tx = new Transaction();
    const borrow = side === 'base' ? client.flashLoans.borrowBaseAsset : client.flashLoans.borrowQuoteAsset;
    const giveBack = side === 'base' ? client.flashLoans.returnBaseAsset : client.flashLoans.returnQuoteAsset;

    const [coin, flashLoanObj] = tx.add(borrow(poolKey, amount));
    tx.add(giveBack(poolKey, amount, coin, flashLoanObj));
    tx.transferObjects([coin], DUMMY_SENDER);
    return tx;
  };
}

async function testAmount(buildTx, amount) {
  const tx = await buildTx(amount);
  const result = await simulate(tx);
  return result;
}

async function bisect(buildTx, label) {
  console.log(`Bisecting real liquidity ceiling for ${label} ...`);
  let lo = 0;
  let hi = 1; // will grow until we find a failing amount
  let hiResult = await testAmount(buildTx, hi);
  while (hiResult.success) {
    lo = hi;
    hi *= 4;
    hiResult = await testAmount(buildTx, hi);
    if (hi > 1e12) throw new Error('Amount grew unreasonably large — something else is wrong');
  }
  // Now lo succeeds (or is 0), hi fails. Narrow down.
  for (let i = 0; i < 24 && hi - lo > Math.max(1, lo * 0.0005); i++) {
    const mid = lo + (hi - lo) / 2;
    const r = await testAmount(buildTx, mid);
    if (r.success) lo = mid;
    else hi = mid;
  }
  console.log(`Ceiling for ${label}: succeeds up to ~${lo.toLocaleString()}, fails at ~${hi.toLocaleString()}`);
  return { lo, hi };
}

// --- CLI ---
const args = process.argv.slice(2);
const protocol = args[0];
const target = args[1];
const bisectFlag = args.includes('--bisect');
const sideArg = (args.find((a) => a.startsWith('--side=')) || '--side=quote').split('=')[1];
const amountArg = args[2] && !args[2].startsWith('--') ? Number(args[2]) : null;

if (!protocol || !target || (!bisectFlag && amountArg == null)) {
  console.error(
    'Usage:\n' +
      '  node test-flashloan.mjs navi <SYMBOL> <amount>\n' +
      '  node test-flashloan.mjs navi <SYMBOL> --bisect\n' +
      '  node test-flashloan.mjs deepbook <POOL_KEY> <amount> [--side=base|quote]\n' +
      '  node test-flashloan.mjs deepbook <POOL_KEY> --bisect [--side=base|quote]',
  );
  process.exit(1);
}

let buildTx;
if (protocol === 'navi') {
  buildTx = (amt) => buildNaviTx(target, amt)();
} else if (protocol === 'deepbook') {
  buildTx = (amt) => buildDeepBookTx(target, amt, sideArg)();
} else {
  console.error(`Unknown protocol "${protocol}". Use "navi" or "deepbook".`);
  process.exit(1);
}

if (bisectFlag) {
  await bisect(buildTx, `${protocol} ${target}${protocol === 'deepbook' ? ' (' + sideArg + ')' : ''}`);
} else {
  const result = await testAmount(buildTx, amountArg);
  console.log(
    `${protocol} ${target} borrow ${amountArg.toLocaleString()}: `,
    result.success ? '✅ SUCCESS' : `❌ FAILED — ${result.error}`,
  );
}
