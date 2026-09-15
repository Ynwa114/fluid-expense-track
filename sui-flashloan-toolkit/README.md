# Sui Flash Loan Testing Toolkit

Tests whether NAVI and DeepBook v3 (Sui) actually have enough liquidity for a flash
loan of a given size — by building the real borrow+repay transaction and asking Sui's
public simulator "would this succeed against current chain state?" Also includes an
Aave v3 (Ethereum) reader for scale comparison.

**Everything here is read-only / dry-run.** Nothing is signed, nothing is broadcast,
no wallet or private key is needed, no gas is spent, no real funds move. Safe to run
against mainnet freely.

## Why this exists (context for whoever picks this up)

Reading a pool's advertised TVL or an indexer's "available liquidity" number is not
the same as knowing whether a specific flash loan amount will actually succeed:

- NAVI's API reports `total_supply - total_borrow` as an "available" figure, but
  that's an indexer-derived estimate — the real on-chain check (inside the Move
  contract) can differ by ~1-2% due to lag/rounding. We measured this directly: the
  API said ~$7.39M available at one point, but the actual bisected on-chain ceiling
  was between $7.28M and $7.30M.
- DeepBook has no separate liquidity estimate to worry about (`vaultBalances()` reads
  the literal on-chain object), but as an active order book its balance can move by
  double-digit percentages within seconds due to real trading — so even an exact
  reading can be stale by the time you act on it.

The only way to know for certain whether a given amount will work **right now** is to
actually attempt it (via simulation) and see what the chain says.

## Setup

```bash
npm install
```

Requires Node 18+.

## Scripts

### `liquidity.mjs` — quick liquidity snapshot

```bash
node liquidity.mjs
```

Prints NAVI's reserve state (supply/borrow/utilization per asset) and DeepBook's
live vault balances for the major pools. Fast, but per the caveats above, treat the
NAVI numbers as directional estimates, not exact ceilings.

### `test-flashloan.mjs` — the real test

Builds an actual flash-loan transaction (borrow + repay in one PTB) and simulates it.

```bash
# Test a specific amount
node test-flashloan.mjs navi nUSDC 5000000
node test-flashloan.mjs deepbook SUI_USDC 300000 --side=quote

# Or auto-find the exact live ceiling via binary search
node test-flashloan.mjs navi nUSDC --bisect
node test-flashloan.mjs deepbook SUI_USDC --bisect --side=quote
```

**NAVI `<SYMBOL>` options:** `Sui`, `USDT`, `WETH`, `vSui`, `WBTC`, `nUSDC` (this is
what shows as plain "USDC" in NAVI's UI — the native/Circle-issued one), `wUSDC`
(Wormhole-bridged, a much smaller and separate pool), and others. Full list:

```bash
node -e "import('navi-sdk').then(({pool})=>console.log(Object.keys(pool)))"
```

Note: amounts are assumed 6-decimal (USDC/USDT-style) in the script's conversion —
if you test `Sui`, `WBTC`, or `vSui`, edit the `1e6` in `buildNaviTx()` to the right
decimals (SUI-family is 9, WBTC is 8).

**DeepBook `<POOL_KEY>` options:** `SUI_USDC`, `USDT_USDC`, `DEEP_SUI`, `DEEP_USDC`,
`WUSDC_USDC`, etc. Full list in `mainnetPools` from `@mysten/deepbook-v3`. `--side`
picks which leg of the pair you're borrowing (default `quote`).

**Reading the output:** a `MoveAbort` in `balance::split` (NAVI) or in
`vault::borrow_flashloan_*` (DeepBook) means insufficient liquidity — that's the
signal you're testing for. Any other error (e.g. `UnusedValueWithoutDrop`) means a
bug in the test script itself, not a liquidity finding — the borrowed/leftover
objects have to be fully consumed or Sui rejects the transaction before it even
checks liquidity. See inline comments in `test-flashloan.mjs`.

### `aave-usdc.mjs` — Ethereum comparison

```bash
node aave-usdc.mjs
```

Reads Aave v3's live USDC reserve on Ethereum mainnet directly from the Pool
contract (cash held by the aToken, not an indexer) — for sizing context. As of
writing, Aave's flash-loanable USDC is roughly 15-25x NAVI's and 2-3 orders of
magnitude more than DeepBook's SUI/USDC pool. Also decodes the reserve config
bitmap to confirm flash loans are actually enabled/unpaused and that governance
caps aren't the binding constraint (they're well above current usage).

## Extending this

- **More assets/pools:** add entries to the `wanted` list in `liquidity.mjs`, or
  just pass a different symbol/pool key to `test-flashloan.mjs` — no code changes
  needed there.
- **Testing with slippage/an intermediate swap:** the current test repays with the
  exact same object it borrowed. A real strategy that swaps the borrowed asset
  before repaying should be modeled explicitly if you need to size for that risk —
  this toolkit only tells you the liquidity ceiling, not execution risk from price
  impact.
- **Matching this rigor on Aave:** `aave-usdc.mjs` reads cash balance directly
  (which is what actually bounds a flash loan there, since a repaid flash loan
  never touches the borrow cap), but doesn't attempt an actual flash loan the way
  `test-flashloan.mjs` does for Sui. Aave requires the receiver to be a *contract*
  implementing a callback (`executeOperation`), so doing an equivalent dry-run
  needs either a deployed receiver contract or an `eth_call` with a state override
  to fake one in — more setup than an EOA-callable Sui PTB, but doable if we need
  the same level of certainty there.
