// Reads LIVE Aave v3 (Ethereum mainnet) USDC reserve data for scale comparison
// against the Sui numbers from liquidity.mjs / test-flashloan.mjs.
// Read-only: no signing, no wallet, no gas spent, uses a public RPC.
//
// Usage: node aave-usdc.mjs

import { createPublicClient, http, formatUnits, getAddress } from 'viem';
import { mainnet } from 'viem/chains';

const client = createPublicClient({ chain: mainnet, transport: http('https://ethereum.publicnode.com') });

const POOL = getAddress('0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2'); // Aave V3 Pool proxy
const USDC = getAddress('0xA0b86991c6218b36C1d19D4a2e9Eb0cE3606eB48');

const poolAbi = [
  {
    name: 'getReserveData',
    type: 'function',
    stateMutability: 'view',
    inputs: [{ name: 'asset', type: 'address' }],
    outputs: [
      {
        type: 'tuple',
        components: [
          { name: 'configuration', type: 'tuple', components: [{ name: 'data', type: 'uint256' }] },
          { name: 'liquidityIndex', type: 'uint128' },
          { name: 'currentLiquidityRate', type: 'uint128' },
          { name: 'variableBorrowIndex', type: 'uint128' },
          { name: 'currentVariableBorrowRate', type: 'uint128' },
          { name: 'currentStableBorrowRate', type: 'uint128' },
          { name: 'lastUpdateTimestamp', type: 'uint40' },
          { name: 'id', type: 'uint16' },
          { name: 'aTokenAddress', type: 'address' },
          { name: 'stableDebtTokenAddress', type: 'address' },
          { name: 'variableDebtTokenAddress', type: 'address' },
          { name: 'interestRateStrategyAddress', type: 'address' },
          { name: 'accruedToTreasury', type: 'uint128' },
          { name: 'unbacked', type: 'uint128' },
          { name: 'isolationModeTotalDebt', type: 'uint128' },
        ],
      },
    ],
  },
  { name: 'FLASHLOAN_PREMIUM_TOTAL', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint128' }] },
];

const erc20Abi = [
  { name: 'balanceOf', type: 'function', stateMutability: 'view', inputs: [{ name: 'a', type: 'address' }], outputs: [{ type: 'uint256' }] },
  { name: 'totalSupply', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint256' }] },
  { name: 'decimals', type: 'function', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint8' }] },
];

const reserveData = await client.readContract({ address: POOL, abi: poolAbi, functionName: 'getReserveData', args: [USDC] });
const { aTokenAddress, variableDebtTokenAddress } = reserveData;

const [cash, deposited, borrowed, decimals, premium] = await Promise.all([
  client.readContract({ address: USDC, abi: erc20Abi, functionName: 'balanceOf', args: [aTokenAddress] }),
  client.readContract({ address: aTokenAddress, abi: erc20Abi, functionName: 'totalSupply' }),
  client.readContract({ address: variableDebtTokenAddress, abi: erc20Abi, functionName: 'totalSupply' }),
  client.readContract({ address: USDC, abi: erc20Abi, functionName: 'decimals' }),
  client.readContract({ address: POOL, abi: poolAbi, functionName: 'FLASHLOAN_PREMIUM_TOTAL' }),
]);

const fmt = (v) => Number(formatUnits(v, decimals)).toLocaleString('en-US', { maximumFractionDigits: 2 });

console.log('=== Aave v3 (Ethereum mainnet) — USDC reserve, live ===');
console.log('Total USDC deposited:', fmt(deposited));
console.log('Total USDC borrowed:', fmt(borrowed));
console.log('Flash-loan ceiling (cash in aToken contract):', fmt(cash));
console.log('Utilization:', ((Number(borrowed) / Number(deposited)) * 100).toFixed(2) + '%');
console.log('Flash loan fee:', (Number(premium) / 100).toFixed(4) + '%');

const cfg = reserveData.configuration.data;
const bit = (p) => ((cfg >> BigInt(p)) & 1n) === 1n;
const field = (p, bits) => (cfg >> BigInt(p)) & ((1n << BigInt(bits)) - 1n);
console.log('\nflashLoanEnabled:', bit(63), '| isPaused:', bit(60), '| isFrozen:', bit(57));
console.log('borrowCap (whole USDC, 0=none):', field(80, 36).toString());
console.log('supplyCap (whole USDC, 0=none):', field(116, 36).toString());
