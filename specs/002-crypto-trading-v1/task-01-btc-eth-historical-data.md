# Task 01 — BTC/ETH Historical OHLCV Data

## Status
Pending

## Owner
Codex agent

## Context

The current dataset (`data/trading/sample_ohlcv.csv`) is 40 rows of synthetic linear price data. It is only used for smoke tests. For the crypto trading domain to be meaningful, we need real historical OHLCV data for BTC and ETH.

The platform is offline-first. Data must be committed as static CSV files — no runtime API calls.

## Task

Generate two deterministic CSV files using a synthetic but realistic crypto-like price model:

- `data/trading/btc_usdt_1d.csv` — 1000 rows of daily BTC/USDT price data
- `data/trading/eth_usdt_1d.csv` — 1000 rows of daily ETH/USDT price data

These are **not** fetched from a live API. Generate them using a seeded random walk with realistic parameters (see below), so the data is deterministic and reproducible.

## CSV Format

Must match the existing format exactly:

```
timestamp,open,high,low,close,volume
2020-01-01,7200.00,7350.00,7150.00,7300.00,25000000.00
...
```

- `timestamp`: YYYY-MM-DD, daily cadence starting 2020-01-01
- `open`, `high`, `low`, `close`: floats rounded to 2 decimal places
- `volume`: float, daily USD volume
- `high >= max(open, close)` always
- `low <= min(open, close)` always

## Generation Parameters

### BTC
- Starting price: 7200.00
- Daily drift: 0.0003 (slight upward bias)
- Daily volatility: 0.025 (2.5% daily std dev)
- Volume: normal around 25_000_000 with std 5_000_000, floor 5_000_000
- Seed: 42

### ETH
- Starting price: 130.00
- Daily drift: 0.0004
- Daily volatility: 0.032
- Volume: normal around 10_000_000 with std 2_000_000, floor 1_000_000
- Seed: 43

### Price walk logic (per row)

```python
import random
rng = random.Random(seed)
log_return = rng.gauss(drift, volatility)
close = prev_close * exp(log_return)
open_ = prev_close * exp(rng.gauss(0, volatility * 0.3))
high = max(open_, close) * (1 + abs(rng.gauss(0, volatility * 0.5)))
low = min(open_, close) * (1 - abs(rng.gauss(0, volatility * 0.5)))
volume = max(floor, rng.gauss(avg_volume, std_volume))
```

## Generator Script

Create `scripts/generate_crypto_data.py` that produces both files when run:

```bash
uv run python scripts/generate_crypto_data.py
```

The script must be idempotent (overwrite if files exist). It must use only the standard library (no numpy, pandas, or external deps).

## Acceptance Criteria

- [ ] `data/trading/btc_usdt_1d.csv` exists with exactly 1000 data rows + header
- [ ] `data/trading/eth_usdt_1d.csv` exists with exactly 1000 data rows + header
- [ ] All rows satisfy `high >= max(open, close)` and `low <= min(open, close)`
- [ ] Both files are committed (not in .gitignore)
- [ ] Running the script twice produces identical output
- [ ] `scripts/generate_crypto_data.py` runs with `uv run python` and no external deps
- [ ] Existing `data/trading/sample_ohlcv.csv` is NOT modified

## Files to Create

- `data/trading/btc_usdt_1d.csv`
- `data/trading/eth_usdt_1d.csv`
- `scripts/generate_crypto_data.py`

## Files to NOT Touch

- `domains/trading/adapter.py`
- `scoring/metrics.py`
- `tests/`
- Any existing CSV files
