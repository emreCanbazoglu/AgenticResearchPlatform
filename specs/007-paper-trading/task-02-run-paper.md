# Task 02 — run_paper.py: Scheduler Loop and Output

## Status
Pending

## Owner
Codex agent

## Depends On
Task 01 — `PaperSession`, `PaperSessionConfig`, `fetch_candles` must exist

## Context

`run_paper.py` is the live entry point. It creates the Director + Workers, then
enters a loop: sleep until the next 30-minute UTC boundary, run one cycle, print
results, save state. Ctrl+C exits cleanly.

Unlike `run_session.py` (which runs all cycles at once on static data), `run_paper.py`
runs one cycle per real-world 30-minute window, forever.

## Task

### 1. Create `run_paper.py` at project root

**Configuration block** (constants at top of file):

```python
SYMBOL              = "BTCUSDT"
INTERVAL            = "30m"
CYCLE_SIZE          = 1       # candles per eval cycle — 1 = evaluate on the just-closed candle
LOOKBACK_SIZE       = 200     # candles for self-tuning window
N_TUNE_CANDIDATES   = 8
TOTAL_BUDGET        = 30_000.0
CHECKPOINT_PATH     = "paper_session.json"
SEED                = 42

# Realistic microstructure defaults
POSITION_SIZE_FRACTION = 0.95
SLIPPAGE_RATE          = 0.0005
```

Note: `CYCLE_SIZE=1` for paper trading — each real 30-minute bar is one evaluation
point. The workers tune on the last 200 bars and evaluate on the just-closed bar.

**Worker definitions** (same as `run_session.py` but with slippage + fraction):

```python
workers = [
    WorkerAgent(
        strategy_id="ma_crossover_v1",
        search_space={"fast_window": (2, 20), "slow_window": (5, 60)},
        optimizer=make_optimizer("bayesian", search_space=..., seed=SEED),
        seed=SEED,
        virtual_budget=10_000.0,
        position_size_fraction=POSITION_SIZE_FRACTION,
        slippage_rate=SLIPPAGE_RATE,
    ),
    WorkerAgent(
        strategy_id="rsi_v1",
        search_space={"period": (5, 30), "overbought": (60, 80), "oversold": (20, 40)},
        optimizer=make_optimizer("bayesian", search_space=..., seed=SEED + 1),
        seed=SEED + 1,
        virtual_budget=10_000.0,
        position_size_fraction=POSITION_SIZE_FRACTION,
        slippage_rate=SLIPPAGE_RATE,
    ),
    WorkerAgent(
        strategy_id="macd_v1",
        search_space={"fast_period": (5, 15), "slow_period": (20, 40), "signal_period": (5, 15)},
        optimizer=make_optimizer("bayesian", search_space=..., seed=SEED + 2),
        seed=SEED + 2,
        virtual_budget=10_000.0,
        position_size_fraction=POSITION_SIZE_FRACTION,
        slippage_rate=SLIPPAGE_RATE,
    ),
]
```

**`sleep_until_next_boundary(interval_minutes: int) -> None`** — module-level function

Calculates seconds until the next `interval_minutes` UTC boundary and sleeps.
Prints: `"Next cycle in {seconds}s  (at {hh:mm} UTC)"`.

```python
import datetime, time

def sleep_until_next_boundary(interval_minutes: int = 30) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    minutes_past = now.minute % interval_minutes
    seconds_past = minutes_past * 60 + now.second
    wait = interval_minutes * 60 - seconds_past
    next_time = now + datetime.timedelta(seconds=wait)
    print(f"  Next cycle in {wait}s  (at {next_time.strftime('%H:%M')} UTC)")
    time.sleep(wait)
```

**`print_cycle(summary: CycleSummary, cycle_count: int) -> None`** — module-level function

Formats and prints one cycle's results. Format:

```
Cycle  7  [2024-01-15 14:30 UTC]  │  Pool: $30,512.40 → $30,598.22  (+0.28%)
          │   ma_crossover  $12,210.00   +0.45%  [real]   fast=4 slow=22
          │   rsi_v1        $10,981.44   +0.12%  [real]   period=20 ob=71 os=26
          │   macd_v1        $7,406.78   +0.00%  [virtual] fast=8 slow=24 sig=14
```

**`main()` function:**

```python
def main() -> None:
    config = PaperSessionConfig(
        symbol=SYMBOL, interval=INTERVAL, cycle_size=CYCLE_SIZE,
        lookback_size=LOOKBACK_SIZE, n_tune_candidates=N_TUNE_CANDIDATES,
        checkpoint_path=CHECKPOINT_PATH, total_budget=TOTAL_BUDGET,
    )
    session = PaperSession.load(CHECKPOINT_PATH, workers)

    print_header(session, config)

    try:
        while True:
            sleep_until_next_boundary(30)
            summary = session.run_one_cycle()
            session.save()
            print_cycle(summary, session.cycle_count)
    except KeyboardInterrupt:
        print("\n\nSession interrupted. Final state saved.")
        print_final_summary(session)
```

**`print_header(session, config) -> None`** — prints startup info:
```
Paper Trading Session — BTCUSDT 30m
Checkpoint : paper_session.json  (cycle 0 — fresh start)  [or "resumed from cycle N"]
Budget     : $30,000.00  |  Workers: 3
Cycle size : 1 candle  |  Lookback: 200 candles
Slippage   : 5.0 bps per fill  |  Position size: 95% of allocated budget
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**`print_final_summary(session) -> None`** — same format as `run_session.py` summary.

### 2. Write unit tests in `tests/unit/test_run_paper.py`

```python
def test_sleep_until_next_boundary_calculates_correctly(monkeypatch):
    # Mock datetime.now to return a known time (e.g. 14:17:30 UTC)
    # Mock time.sleep to capture the argument
    # Assert sleep is called with correct seconds to reach next 30m boundary (14:30)
    # Expected: (30 - 17) * 60 - 30 = 750 seconds

def test_sleep_called_for_exact_boundary(monkeypatch):
    # At exactly 14:30:00, sleep should be called with 1800 seconds (full interval)
    # (don't skip — always wait for the next full cycle)
```

### 3. Verify `uv run python run_paper.py --help` or dry-run works

The script must not crash on import. Add a `--dry-run` flag that runs one cycle
immediately (no sleeping) using the last available candles and then exits.
This is the only way to test the script end-to-end without waiting 30 minutes.

```bash
uv run python run_paper.py --dry-run
```

Output should show one cycle report and exit.

## Acceptance Criteria

- [ ] `run_paper.py` exists at project root
- [ ] `uv run python run_paper.py --dry-run` completes without error
- [ ] `--dry-run` fetches live data, runs one cycle, prints report, saves checkpoint, exits
- [ ] Normal mode (`uv run python run_paper.py`) sleeps until next 30m boundary
- [ ] Ctrl+C prints final summary and exits cleanly
- [ ] `paper_session.json` is written after each cycle
- [ ] Resuming (running again after a checkpoint exists) continues from saved state
- [ ] `uv run pytest tests/unit/test_run_paper.py` green
- [ ] `uv run pytest` fully green

## Files to Create

- `run_paper.py`
- `tests/unit/test_run_paper.py`

## Files to NOT Touch

- `core/`
- `domains/`
- `meta/`
- `run_session.py`
- `run_mvp.py`
- Any spec files
