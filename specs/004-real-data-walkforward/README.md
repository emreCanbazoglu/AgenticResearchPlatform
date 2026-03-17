# Spec 004 — Real Data and Walk-Forward Validation

## Goal

Replace the seeded random-walk CSVs with real historical BTC/ETH data from the Binance public API, then add a walk-forward train/test split to the trading adapter so that reported metrics reflect out-of-sample performance.

## Why This Matters

- **Real data**: the synthetic random-walk CSVs produce meaningless research. Strategy scores are not interpretable. Replacing them with real OHLCV data makes every result from this point forward immediately actionable.
- **Walk-forward split**: without a holdout, all reported metrics are in-sample — the optimizer can overfit to the exact data it's tuning on. A 70/30 train/test split makes the reported Sharpe ratio and drawdown trustworthy.

## Tasks

| # | Task | Depends on | Status |
|---|---|---|---|
| 01 | Fetch real Binance OHLCV data | — | Pending |
| 02 | Walk-forward split in adapter | Task 01 (for integration test) | Pending |

Task 01 must complete (or run in parallel) before Task 02's integration test can use real data. The implementation in Task 02 is independent of the data download.

## Definition of Done

- [ ] Both tasks complete
- [ ] `uv run pytest` passes with no failures
- [ ] `data/trading/btc_usdt_1d.csv` and `data/trading/eth_usdt_1d.csv` exist with ≥ 500 rows of real OHLCV
- [ ] `TradingAdapter` accepts `train_ratio` and reports test-split metrics
- [ ] `uv run python run_mvp.py` runs successfully on real BTC data
