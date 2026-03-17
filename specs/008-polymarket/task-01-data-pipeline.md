# Task 01 — Historical Market Data Pipeline

## Status
Pending

## Owner
Codex agent

## Depends On
Nothing — can run in parallel with Task 02

## Context

The backtest engine needs a local store of resolved Polymarket markets with:
1. Market metadata (question, category, creation date, resolution date)
2. Probability time series (price snapshots over the market's lifetime)
3. Resolution outcome (1.0 = YES resolved, 0.0 = NO resolved)

Polymarket provides two data sources:
- **REST API** — live and recent market data, price history for open/recent markets
- **Historical dump** — Polymarket has published CSV/JSON dumps of resolved markets
  on their data portal (data.polymarket.com) and via IPFS

For this task we use the public historical dump, not the live API
(live API is covered in Task 05). This keeps the data pipeline offline-first
and deterministic.

## Data Schema

### `data/polymarket/markets.json`
Array of resolved market objects:
```json
[
  {
    "market_id": "0xabc123...",
    "question": "Will the Fed raise rates in March 2025?",
    "category": "economics",
    "created_at": "2025-01-15T00:00:00Z",
    "resolved_at": "2025-03-20T18:00:00Z",
    "outcome": 1.0,
    "tags": ["fed", "rates", "macro"]
  },
  ...
]
```

### `data/polymarket/price_histories/`
One CSV file per market, named `{market_id}.csv`:
```
timestamp,probability
2025-01-15T00:00:00Z,0.42
2025-01-15T06:00:00Z,0.44
...
2025-03-20T12:00:00Z,0.91
```
Columns: `timestamp` (ISO 8601), `probability` (float 0.0–1.0)

## Files to Create

### `domains/polymarket/__init__.py` (empty)

### `domains/polymarket/data_store.py`

```python
@dataclass
class MarketRecord:
    market_id: str
    question: str
    category: str
    created_at: datetime
    resolved_at: datetime
    outcome: float           # 1.0 = YES, 0.0 = NO
    tags: list[str]

@dataclass
class PricePoint:
    timestamp: datetime
    probability: float

class HistoricalMarketStore:
    def __init__(self, data_dir: str | Path): ...

    def load_all(self) -> list[MarketRecord]:
        """Return all resolved markets sorted by resolved_at ascending."""

    def get_price_series(self, market_id: str) -> list[PricePoint]:
        """Return probability time series for one market."""

    def get_by_category(self, category: str) -> list[MarketRecord]:
        """Filter markets by category string."""

    def get_resolved_before(self, cutoff: datetime) -> list[MarketRecord]:
        """Return markets that resolved before a given date."""

    def get_resolved_between(
        self, start: datetime, end: datetime
    ) -> list[MarketRecord]:
        """Return markets that resolved within a date range."""
```

### `scripts/fetch_polymarket_data.py`

Fetches historical market data from the Polymarket data portal and writes to
`data/polymarket/`. Uses `urllib` only (no `requests`).

```
Endpoints:
  GET https://data.polymarket.com/markets?resolved=true&limit=500
  GET https://clob.polymarket.com/prices-history?market={market_id}&interval=1h

Rate limit: 1 request/second (add time.sleep(1) between calls)
```

CLI:
```bash
# Fetch last 500 resolved markets + their price histories
uv run python scripts/fetch_polymarket_data.py

# Fetch only a specific category
uv run python scripts/fetch_polymarket_data.py --category elections

# Dry-run: print what would be fetched, write nothing
uv run python scripts/fetch_polymarket_data.py --dry-run
```

Output:
```
Fetching resolved markets... 500 found
Writing data/polymarket/markets.json
Fetching price histories: 500/500
  [OK] 0xabc123 — Will the Fed raise rates... (42 price points)
  [SKIP] 0xdef456 — no price history available
Done. 487 markets with price histories written to data/polymarket/
```

### `data/polymarket/sample/` (committed to repo)

A small sample dataset (20–30 resolved markets, manually curated) so tests
can run offline without hitting the API. Include markets across multiple
categories: elections, crypto prices, sports, economics.

## Tests

### `tests/unit/test_data_store.py`

```python
def test_load_all_returns_sorted_by_resolution_date():
    # markets are returned oldest-first

def test_get_price_series_returns_sorted_ascending():
    # price series is chronological

def test_get_by_category_filters_correctly():
    # only returns markets matching category

def test_get_resolved_before_excludes_later_markets():
    # cutoff date respected

def test_empty_price_series_handled():
    # market_id with no price history CSV returns []

def test_market_record_fields_parsed():
    # outcome is float, dates are datetime objects, tags is list[str]
```

### `tests/integration/test_fetch_polymarket_data.py`

```python
def test_fetch_dry_run_prints_without_writing(tmp_path, monkeypatch):
    # monkeypatch urllib to return sample data
    # --dry-run flag writes nothing to disk

def test_fetch_writes_markets_json(tmp_path, monkeypatch):
    # verifies markets.json is created with correct schema

def test_fetch_writes_price_csv_per_market(tmp_path, monkeypatch):
    # verifies price_histories/{market_id}.csv is created
```

## Acceptance Criteria

- [ ] `domains/polymarket/__init__.py` exists
- [ ] `domains/polymarket/data_store.py` with `MarketRecord`, `PricePoint`,
      `HistoricalMarketStore` implemented
- [ ] `data/polymarket/sample/` contains at least 20 resolved markets with
      price histories covering at least 3 categories
- [ ] `scripts/fetch_polymarket_data.py` runnable with `--dry-run` flag
- [ ] `HistoricalMarketStore` correctly loads the sample dataset
- [ ] All unit tests green
- [ ] `uv run pytest` fully green

## Files to NOT Touch

- `domains/trading/`
- `core/`
- `meta/`
- Any existing spec files
