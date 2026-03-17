# Task 01 — PaperSession: State Persistence and Live Candle Loader

## Status
Pending

## Owner
Codex agent

## Context

The backtesting session (`Director.run_session()`) runs all cycles in one shot and
holds all state in memory. For paper trading, cycles happen on a real 30-minute clock.
The process wakes up, runs one cycle, saves state, and exits — or stays alive and loops.

`PaperSession` wraps the `Director` and provides:
1. A live candle loader (fetches the last N candles from Binance)
2. State persistence (saves/loads Director + Worker states to a JSON file)
3. A `run_one_cycle()` method that executes exactly one Director cycle on fresh live data

## Task

### 1. Create `core/multi_agent/paper_session.py`

```python
@dataclass
class PaperSessionConfig:
    symbol: str = "BTCUSDT"
    interval: str = "30m"
    cycle_size: int = 48          # candles evaluated per cycle (1 day at 30m)
    lookback_size: int = 200      # candles used for worker self-tuning window
    n_tune_candidates: int = 8
    checkpoint_path: str = "paper_session.json"
    total_budget: float = 30_000.0


class PaperSession:
    def __init__(self, config: PaperSessionConfig, workers: list[WorkerAgent]) -> None: ...
```

**`fetch_candles(symbol, interval, limit) -> list[float]`** — module-level function

Fetches close prices from the Binance klines endpoint. Reuse the same URL pattern
from `scripts/fetch_crypto_data.py`:
```
GET https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}
```
Returns `list[float]` of close prices (index 4 of each kline row), most recent last.
Raises `RuntimeError` with a clear message on network error or HTTP error.
Standard library only (`urllib.request`, `json`).

**`PaperSession.run_one_cycle() -> CycleSummary`**

```
1. Fetch lookback_size + cycle_size candles from Binance
   (fetches enough for both tune window and eval window in one API call)
2. tune_prices = all_candles[:lookback_size]
3. eval_prices = all_candles[lookback_size:]
   If len(eval_prices) < cycle_size: use all available
4. Execute one Director cycle:
   a. Workers self-tune on tune_prices
   b. Director allocates budgets
   c. Workers run_eval on eval_prices
   d. Director collects P&L, updates total_budget
5. Append CycleSummary to self._history
6. Return the CycleSummary
```

**`PaperSession.save(path: str | None = None) -> None`**

Serialises full session state to JSON:
```json
{
  "config": { "symbol": "BTCUSDT", "interval": "30m", ... },
  "cycle_count": 5,
  "total_budget": 31_200.50,
  "workers": [
    { "strategy_id": "ma_crossover_v1", "current_params": {...},
      "cycle_count": 5, "optimizer_state": {...},
      "position_size_fraction": 0.95, "slippage_rate": 0.0005 },
    ...
  ],
  "history": [
    { "cycle_idx": 0, "total_budget_before": 30000, "total_budget_after": 30241,
      "allocations": {...}, "results": [...] },
    ...
  ]
}
```

Use `json.dumps(..., indent=2)`. Write atomically: write to a `.tmp` file first,
then rename to the target path.

**`PaperSession.load(path: str, workers: list[WorkerAgent]) -> PaperSession`** — classmethod

Loads a checkpoint and restores:
- `total_budget` from the checkpoint
- Each worker's state via `worker.restore(state)`
- `_history` list
- `_cycle_count`

If the checkpoint file does not exist, returns a fresh `PaperSession`.
If the file is malformed JSON, raises `ValueError("corrupt checkpoint: {path}")`.

**`PaperSession.summary() -> dict`** — returns a summary dict for display:
```python
{
    "cycle_count": int,
    "initial_budget": float,      # budget at session start (from first cycle or config)
    "current_budget": float,
    "total_return_pct": float,
    "best_worker": str,           # strategy_id with highest cumulative pnl_pct
    "history_len": int,
}
```

### 2. Write unit tests in `tests/unit/test_paper_session.py`

All tests must mock `fetch_candles` — no real network calls.

```python
def test_run_one_cycle_returns_cycle_summary(monkeypatch):
    # Mock fetch_candles to return 248 synthetic prices
    # Create PaperSession with 3 workers
    # run_one_cycle() returns a CycleSummary with 3 results

def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    # Run 2 cycles, save to tmp_path/session.json
    # Load fresh PaperSession from same file
    # Assert: cycle_count matches, total_budget matches, worker params match

def test_load_missing_file_returns_fresh_session(tmp_path):
    # PaperSession.load("nonexistent.json", workers) returns fresh session
    # cycle_count == 0, total_budget == config.total_budget

def test_load_corrupt_file_raises(tmp_path):
    # Write invalid JSON, assert ValueError on load

def test_budget_updates_after_cycle(monkeypatch):
    # After run_one_cycle(), PaperSession total_budget != initial value
    # (some workers made real P&L)

def test_fetch_candles_parses_binance_response(monkeypatch):
    # Mock urlopen to return a fake Binance klines JSON array
    # Assert fetch_candles returns correct close prices as floats
```

## Acceptance Criteria

- [ ] `core/multi_agent/paper_session.py` exists
- [ ] `fetch_candles(symbol, interval, limit) -> list[float]` works with mocked API
- [ ] `PaperSession.run_one_cycle()` executes one full Director cycle on fetched data
- [ ] `save()` writes atomic JSON checkpoint
- [ ] `load()` restores all state; returns fresh session if file missing
- [ ] No real network calls in tests
- [ ] `uv run pytest tests/unit/test_paper_session.py` green
- [ ] `uv run pytest` fully green

## Files to Create

- `core/multi_agent/paper_session.py`
- `tests/unit/test_paper_session.py`

## Files to NOT Touch

- `core/multi_agent/director.py`
- `core/multi_agent/worker_agent.py`
- `scripts/fetch_crypto_data.py`
- Any spec files
