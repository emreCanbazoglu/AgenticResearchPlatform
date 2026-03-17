# Task 03 — WorkerAgent

## Status
Pending

## Owner
Codex agent

## Depends On
Task 02 — `TradingAdapter.run_on_prices()` must exist

## Context

A WorkerAgent owns a single trading strategy. Each cycle it does two things:
1. **Self-tune** on a lookback window — runs its internal optimizer to find better parameters
2. **Run eval** on the next window — executes its best-known parameters with the budget the Director assigns

If allocated `budget=0` (or below the virtual threshold), the worker runs on a
fixed virtual capital amount instead of contributing to the real pool. It still
reports its score so the Director can reconsider future allocations.

## Data Structures

```python
# core/multi_agent/worker_agent.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class CycleResult:
    strategy_id: str
    cycle_idx: int
    budget_allocated: float    # real budget given by Director (0 if virtual)
    is_virtual: bool           # True when running on virtual capital
    initial_equity: float      # capital used for this eval (real or virtual)
    final_equity: float
    pnl: float                 # final_equity - initial_equity
    pnl_pct: float             # pnl / initial_equity  (e.g. 0.023 = +2.3%)
    score: float               # composite score from scoring engine
    params_used: dict[str, Any]  # strategy parameters used this cycle
    trade_count: int
```

## Task

### 1. Create `core/multi_agent/__init__.py` (empty)

### 2. Create `core/multi_agent/worker_agent.py`

```python
@dataclass
class WorkerAgent:
    strategy_id: str
    search_space: dict[str, tuple[int, int]]
    optimizer: Optimizer        # caller provides — genetic, bayesian, or bandit
    seed: int
    virtual_budget: float = 10_000.0
    commission_rate: float = 0.001

    # Internal mutable state — do NOT set externally
    _current_params: dict[str, Any] = field(default_factory=dict, init=False)
    _cycle_count: int = field(default=0, init=False)
```

**`self_tune(prices, n_candidates=8) -> None`**

Called by the Director before each eval cycle. Uses the optimizer to search for
better parameters on the given price window.

```
1. Ask optimizer for n_candidates via suggest(iteration=_cycle_count, batch_size=n_candidates)
2. For each candidate:
   a. Run TradingAdapter(initial_capital=virtual_budget, commission_rate=...).run_on_prices(
          prices=prices, strategy_id=strategy_id, parameters=candidate.parameters, seed=seed)
   b. Collect (candidate, result.score)
3. Call optimizer.observe(scored_candidates=scored)
4. Set _current_params = parameters of the highest-scoring candidate
5. Increment _cycle_count
```

If `prices` has fewer than 20 rows (not enough to evaluate any strategy),
skip tuning silently and do not increment `_cycle_count`.

If `_current_params` is empty (first cycle, optimizer hasn't suggested yet),
initialise it to the midpoint of each search space dimension before step 1
so that `run_eval` always has valid params to fall back on.

**`run_eval(prices, budget, cycle_idx) -> CycleResult`**

Called by the Director during each eval cycle.

```
1. Determine is_virtual = (budget <= 0)
   actual_capital = virtual_budget if is_virtual else budget
2. Run TradingAdapter(initial_capital=actual_capital, commission_rate=...).run_on_prices(
       prices=prices, strategy_id=strategy_id,
       parameters=_current_params, seed=seed)
3. Return CycleResult(
       strategy_id, cycle_idx,
       budget_allocated=budget,
       is_virtual=is_virtual,
       initial_equity=actual_capital,
       final_equity=result.metrics["final_equity"],
       pnl=result.metrics["final_equity"] - actual_capital,
       pnl_pct=(result.metrics["final_equity"] - actual_capital) / actual_capital,
       score=result.score,
       params_used=dict(_current_params),
       trade_count=int(result.metrics["trade_count"]),
   )
```

If `prices` has fewer than 20 rows, return a zero-pnl CycleResult
(pnl=0, pnl_pct=0, score=0, trade_count=0).

**`checkpoint() -> dict`** — returns JSON-serialisable state:
```json
{
  "strategy_id": "...",
  "current_params": {...},
  "cycle_count": 5,
  "optimizer_state": {...}   // from optimizer.checkpoint()
}
```

**`restore(state: dict) -> None`** — restores from checkpoint.

### 3. Write unit tests in `tests/unit/test_worker_agent.py`

```python
def test_self_tune_updates_params(tmp_path):
    # After self_tune on 100 prices, _current_params is a non-empty dict
    # with keys from search_space

def test_run_eval_uses_current_params():
    # After self_tune, run_eval uses the params found (not zeroes)

def test_zero_budget_is_virtual():
    # run_eval(prices, budget=0, cycle_idx=0).is_virtual == True
    # run_eval(prices, budget=5000, cycle_idx=0).is_virtual == False

def test_virtual_pnl_does_not_affect_real_budget():
    # CycleResult.is_virtual=True means budget_allocated=0
    # The Director must NOT add virtual pnl to total_budget (tested in director tests)

def test_checkpoint_restore_roundtrip():
    # tune N cycles → checkpoint → restore into fresh agent → run_eval → same result

def test_short_price_list_handled_gracefully():
    # prices with 10 rows → self_tune no-ops, run_eval returns zero-pnl result
```

## Acceptance Criteria

- [ ] `core/multi_agent/__init__.py` exists (empty)
- [ ] `core/multi_agent/worker_agent.py` exists with `CycleResult` + `WorkerAgent`
- [ ] `WorkerAgent.self_tune()` runs optimizer loop and updates `_current_params`
- [ ] `WorkerAgent.run_eval()` returns `CycleResult` with correct `is_virtual` flag
- [ ] Budget=0 → virtual mode using `virtual_budget`
- [ ] Short price lists handled without exceptions
- [ ] `checkpoint()` / `restore()` roundtrip works
- [ ] `uv run pytest tests/unit/test_worker_agent.py` green
- [ ] `uv run pytest` fully green

## Files to Create

- `core/multi_agent/__init__.py`
- `core/multi_agent/worker_agent.py`
- `tests/unit/test_worker_agent.py`

## Files to NOT Touch

- `domains/trading/adapter.py`
- `meta/`
- `core/orchestration/`
- `core/execution/`
- Any spec files
