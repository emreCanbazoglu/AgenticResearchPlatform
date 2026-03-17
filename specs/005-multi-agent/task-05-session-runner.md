# Task 05 — Session Runner Entry Point

## Status
Pending

## Owner
Codex agent

## Depends On
Task 04 — `Director`, `SessionResult`, `CycleSummary` must exist

## Context

`run_mvp.py` runs single-strategy campaigns. We need a separate entry point
`run_session.py` that demonstrates the full multi-agent Director/Worker system
in action: three workers (MA, RSI, MACD), one Director with a shared budget,
running on real BTC 30-minute data.

## Task

### 1. Create `run_session.py`

```python
#!/usr/bin/env python3
"""
Multi-agent trading session.

Three strategy workers (MA crossover, RSI, MACD) compete for a shared $30,000
budget over rolling 30-minute cycles on real BTC data.
The Director reallocates capital each cycle using UCB1 — winners get more,
losers run on virtual capital until they recover.
"""
```

**Configuration at the top of the file (not CLI args):**

```python
DATASET        = "data/trading/btc_usdt_30m.csv"
FALLBACK_DATA  = "data/trading/btc_usdt_1d.csv"   # used if 30m file missing
TOTAL_BUDGET   = 30_000.0
SEED           = 42
CYCLE_SIZE     = 48     # candles per cycle (~1 trading day at 30m)
LOOKBACK_SIZE  = 200    # candles for tuning window
N_TUNE_CANDS   = 8      # candidates per optimizer call per tune phase
MIN_BUDGET_PCT = 0.05   # workers below 5% of pool run virtually
EXPLORATION_C  = 1.0    # UCB1 exploration coefficient
```

**Workers to create:**

```python
workers = [
    WorkerAgent(
        strategy_id="ma_crossover_v1",
        search_space={"fast_window": (2, 20), "slow_window": (5, 60)},
        optimizer=make_optimizer("bayesian", search_space=..., seed=SEED),
        seed=SEED,
        virtual_budget=10_000.0,
    ),
    WorkerAgent(
        strategy_id="rsi_v1",
        search_space={"period": (5, 30), "overbought": (60, 80), "oversold": (20, 40)},
        optimizer=make_optimizer("bayesian", search_space=..., seed=SEED + 1),
        seed=SEED + 1,
        virtual_budget=10_000.0,
    ),
    WorkerAgent(
        strategy_id="macd_v1",
        search_space={"fast_period": (5, 15), "slow_period": (20, 40), "signal_period": (5, 15)},
        optimizer=make_optimizer("bayesian", search_space=..., seed=SEED + 2),
        seed=SEED + 2,
        virtual_budget=10_000.0,
    ),
]
```

**Loading prices:** Read the `close` column from the dataset CSV into a
`list[float]`. If `DATASET` doesn't exist, fall back to `FALLBACK_DATA` and
print a warning.

**Output format:**

```
Multi-Agent Session — BTC/USDT 30m
Dataset : data/trading/btc_usdt_30m.csv  (952 candles)
Budget  : $30,000.00  |  Workers: 3  |  Cycles: 15
Cycle size: 48 candles  |  Lookback: 200 candles
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cycle  00  │ Pool: $30,000 → $30,241  (+0.80%)
           │   ma_crossover  $12,000  +1.20%  [real]   params: fast=4 slow=22
           │   rsi_v1        $10,000  +0.50%  [real]   params: period=14 ob=70 os=30
           │   macd_v1        $8,000  +0.71%  [real]   params: fast=8 slow=21 sig=9
Cycle  01  │ Pool: $30,241 → $30,089  (-0.50%)
           │   ma_crossover  $14,512  +0.82%  [real]   ...
           │   rsi_v1         $9,812  -2.10%  [real]   ...
           │   macd_v1            $0  +0.30%  [virtual] ...
...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SESSION SUMMARY
  Initial pool  :  $30,000.00
  Final pool    :  $31,850.00
  Total return  :  +6.17%
  Cycles run    :  15
  Winner        :  ma_crossover_v1  (highest cumulative real P&L)

  Final parameters (best found):
    ma_crossover_v1  :  fast=4  slow=22
    rsi_v1           :  period=14  overbought=70  oversold=30
    macd_v1          :  fast=8  slow=21  signal=9
```

Use `$` formatting with 2 decimal places for money. Use `+/-` prefix for
percentages. Mark each worker line with `[real]` or `[virtual]`.

### 2. Verify `uv run pytest` is still fully green after this task

No new tests are required for the entry point itself — it is tested implicitly
by the integration test in task 04. Just confirm all existing tests pass.

## Acceptance Criteria

- [ ] `run_session.py` exists at project root
- [ ] `uv run python run_session.py` completes without error
- [ ] Output shows per-cycle table with pool before/after and worker breakdown
- [ ] Output shows SESSION SUMMARY with initial/final pool, return, winner, final params
- [ ] Falls back to daily data gracefully if 30m file missing
- [ ] `uv run pytest` fully green

## Files to Create

- `run_session.py`

## Files to NOT Touch

- `run_mvp.py` (keep it working)
- `core/`
- `domains/`
- `meta/`
- Any spec files
