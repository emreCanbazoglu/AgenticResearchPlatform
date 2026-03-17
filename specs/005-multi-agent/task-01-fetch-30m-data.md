# Task 01 — Fetch 30-Minute OHLCV Data

## Status
Pending

## Owner
Codex agent

## Context

`scripts/fetch_crypto_data.py` currently fetches daily candles only (`interval=1d`).
The multi-agent session needs 30-minute candles so that a single "cycle" covers
a meaningful intraday window. The Binance API supports `interval=30m` with no
authentication.

1000 rows of 30-minute candles = ~20 trading days of data.

## Task

### 1. Update `scripts/fetch_crypto_data.py`

Add 30-minute symbols to `OUTPUT_FILES` alongside the existing daily ones:

```python
OUTPUT_FILES = {
    "BTCUSDT":    DATA_DIR / "btc_usdt_1d.csv",
    "ETHUSDT":    DATA_DIR / "eth_usdt_1d.csv",
    "BTCUSDT_30m": DATA_DIR / "btc_usdt_30m.csv",
    "ETHUSDT_30m": DATA_DIR / "eth_usdt_30m.csv",
}
```

The Binance klines endpoint uses a query parameter `interval` to select granularity.
Modify `fetch_klines` (or `fetch_and_write_symbol`) to accept an optional `interval`
parameter that overrides the module-level `INTERVAL` constant:

```python
def fetch_klines(symbol: str, interval: str = INTERVAL, limit: int = LIMIT) -> list[list[object]]:
    url = f"{BASE_URL}?symbol={symbol}&interval={interval}&limit={limit}"
    ...
```

Update `main()` so that symbols ending in `_30m` are fetched with `interval="30m"`,
and the actual Binance symbol used is the prefix before `_30m` (e.g. `"BTCUSDT_30m"`
→ Binance symbol `"BTCUSDT"`, interval `"30m"`).

The CSV format must remain identical: `open_time,open,high,low,close,volume`.

### 2. Update the unit tests in `tests/unit/test_fetch_crypto_data.py`

The existing two tests mock `LIMIT=3` and test CSV writing. They must continue to
pass unchanged.

Add two new tests that verify 30-minute fetch works:

```python
def test_30m_interval_used_in_url(monkeypatch):
    # Capture the URL passed to urlopen
    # Assert it contains "interval=30m" when symbol ends in _30m

def test_30m_output_file_has_correct_header(tmp_path, monkeypatch):
    # Mock API, write to tmp file, assert header = open_time,open,high,low,close,volume
```

### 3. Run the script to produce the actual files

After implementation the agent must run:
```bash
uv run python scripts/fetch_crypto_data.py
```
and confirm all four files are written:
- `data/trading/btc_usdt_1d.csv`
- `data/trading/eth_usdt_1d.csv`
- `data/trading/btc_usdt_30m.csv`
- `data/trading/eth_usdt_30m.csv`

## Acceptance Criteria

- [ ] `scripts/fetch_crypto_data.py` fetches both `1d` and `30m` candles
- [ ] `data/trading/btc_usdt_30m.csv` exists with ≥ 500 rows after running the script
- [ ] `data/trading/eth_usdt_30m.csv` exists with ≥ 500 rows after running the script
- [ ] Existing daily CSVs are not changed in structure
- [ ] All unit tests in `tests/unit/test_fetch_crypto_data.py` pass
- [ ] `uv run pytest tests/unit/test_fetch_crypto_data.py` green

## Files to Modify

- `scripts/fetch_crypto_data.py`
- `tests/unit/test_fetch_crypto_data.py`

## Files to NOT Touch

- `domains/`
- `core/`
- `meta/`
- `data/trading/btc_usdt_1d.csv`
- `data/trading/eth_usdt_1d.csv`
- Any spec files
