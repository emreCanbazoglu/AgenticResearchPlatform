# Task 02 — Wire Realism Params into WorkerAgent and run_session.py

## Status
Pending

## Owner
Codex agent

## Depends On
Task 01 — `TradingAdapter` must have `position_size_fraction` and `slippage_rate` fields

## Context

`TradingAdapter` now has `position_size_fraction` and `slippage_rate` fields (from Task 01),
but `WorkerAgent` still instantiates `TradingAdapter` with only `initial_capital` and
`commission_rate`. This task surfaces both new params up through WorkerAgent so that
different workers can have different microstructure assumptions, and updates `run_session.py`
to use realistic non-zero defaults.

## Task

### 1. Update `core/multi_agent/worker_agent.py`

Add two new fields to `WorkerAgent`:

```python
@dataclass
class WorkerAgent:
    strategy_id: str
    search_space: dict[str, tuple[int, int]]
    optimizer: Optimizer
    seed: int
    virtual_budget: float = 10_000.0
    commission_rate: float = 0.001
    position_size_fraction: float = 1.0    # NEW — fraction of cash to invest per trade
    slippage_rate: float = 0.0             # NEW — one-way market impact per fill
```

Wherever `WorkerAgent` instantiates `TradingAdapter` (both in `self_tune` and `run_eval`),
pass through the new fields:

```python
TradingAdapter(
    initial_capital=...,
    commission_rate=self.commission_rate,
    position_size_fraction=self.position_size_fraction,
    slippage_rate=self.slippage_rate,
)
```

Include both new fields in `checkpoint()` output and restore them in `restore()`.

### 2. Update `run_session.py`

Change the three `WorkerAgent` instantiations to use realistic defaults:

```python
workers = [
    WorkerAgent(
        strategy_id="ma_crossover_v1",
        ...
        position_size_fraction=0.95,   # deploy 95% of allocated budget per trade
        slippage_rate=0.0005,          # 5 bps per fill (realistic for BTC/USDT on Binance)
    ),
    WorkerAgent(
        strategy_id="rsi_v1",
        ...
        position_size_fraction=0.95,
        slippage_rate=0.0005,
    ),
    WorkerAgent(
        strategy_id="macd_v1",
        ...
        position_size_fraction=0.95,
        slippage_rate=0.0005,
    ),
]
```

### 3. Update the session output in `run_session.py`

Add a cost breakdown line to the SESSION SUMMARY showing total slippage paid
across all workers across all cycles:

```
  Cost breakdown (across all real cycles):
    Total commission paid  :  $XX.XX
    Total slippage paid    :  $XX.XX
    Total friction         :  $XX.XX  (commission + slippage)
```

To collect this, accumulate `slippage_paid` and `commission_paid` from the metrics
stored in each `CycleResult`. Since `CycleResult` currently only stores a subset of
metrics, either:
- Option A: add `commission_paid: float` and `slippage_paid: float` fields to `CycleResult`
- Option B: store `extra_metrics: dict` on `CycleResult` for arbitrary metrics passthrough

Use **Option A** — explicit fields are cleaner. Add them to `CycleResult` in `worker_agent.py`
and populate them from `result.metrics` in `run_eval()`.

### 4. Write unit tests in `tests/unit/test_worker_realism.py`

```python
def test_worker_passes_slippage_to_adapter():
    # WorkerAgent(slippage_rate=0.01).run_eval(prices, budget, 0)
    # result.slippage_paid should be > 0 when at least one trade occurred

def test_worker_passes_position_fraction_to_adapter():
    # WorkerAgent(position_size_fraction=0.5).run_eval(prices, budget, 0)
    # final_equity > 0 and cash was NOT fully depleted after first buy

def test_default_worker_has_zero_slippage():
    # WorkerAgent() defaults → result.slippage_paid == 0.0

def test_checkpoint_includes_realism_params():
    # checkpoint()["position_size_fraction"] == worker.position_size_fraction
    # checkpoint()["slippage_rate"] == worker.slippage_rate

def test_restore_preserves_realism_params():
    # Create worker, checkpoint, restore into new worker, assert fields match
```

## Acceptance Criteria

- [ ] `WorkerAgent` has `position_size_fraction` and `slippage_rate` fields
- [ ] Both are passed to `TradingAdapter` in `self_tune` and `run_eval`
- [ ] Both are included in `checkpoint()` / `restore()`
- [ ] `CycleResult` has `commission_paid` and `slippage_paid` float fields
- [ ] `run_session.py` uses `position_size_fraction=0.95` and `slippage_rate=0.0005`
- [ ] SESSION SUMMARY prints cost breakdown
- [ ] All existing tests pass (defaults preserve old behaviour)
- [ ] `uv run pytest tests/unit/test_worker_realism.py` green
- [ ] `uv run pytest` fully green
- [ ] `uv run python run_session.py` runs and shows cost breakdown

## Files to Modify

- `core/multi_agent/worker_agent.py`
- `run_session.py`

## Files to Create

- `tests/unit/test_worker_realism.py`

## Files to NOT Touch

- `domains/trading/adapter.py`
- `core/multi_agent/director.py`
- `meta/`
- Any spec files
