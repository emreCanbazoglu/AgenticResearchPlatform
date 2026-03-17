# Task 04 — Director and Budget Allocation

## Status
Pending

## Owner
Codex agent

## Depends On
Task 03 — `WorkerAgent`, `CycleResult` must exist

## Context

The Director is the orchestrator of the multi-agent session. It holds the shared
capital pool and decides each cycle how much budget to assign to each worker.

**Budget allocation uses UCB1:**
```
ucb1(worker) = mean_pnl_pct(worker) + C * sqrt(log(total_cycles + 1) / (obs_count(worker) + 1))
```
- `C = 1.0` exploration coefficient (configurable)
- Workers that have never been evaluated get score `+inf` (explore first)
- Scores are converted to budget fractions: each worker's share is proportional
  to its `max(0, ucb1_score)`. If all scores are non-positive, revert to equal split.
- Any worker whose proportional share falls below `min_budget_fraction` of total
  receives `budget=0` and runs in virtual mode.

**Cycle structure:**
```
For each cycle i:
  tune_end   = i * cycle_size
  tune_start = max(0, tune_end - lookback_size)
  eval_start = tune_end
  eval_end   = eval_start + cycle_size

  tune_prices = all_prices[tune_start:tune_end]   # may be empty for cycle 0
  eval_prices = all_prices[eval_start:eval_end]

  1. Workers self_tune on tune_prices (parallel via ThreadPoolExecutor)
  2. Director allocates budgets based on UCB1 scores
  3. Workers run_eval on eval_prices (parallel via ThreadPoolExecutor)
  4. Real P&L flows back: total_budget += sum(r.pnl for r in results if not r.is_virtual)
  5. Director observes pnl_pct for each worker (updates UCB1 state)
  6. Append CycleSummary to session history
```

## Data Structures

```python
# core/multi_agent/director.py

@dataclass
class CycleSummary:
    cycle_idx: int
    total_budget_before: float
    total_budget_after: float
    allocations: dict[str, float]    # strategy_id -> budget assigned
    results: list[CycleResult]       # one per worker

    @property
    def best_worker(self) -> str:
        # strategy_id of the worker with highest pnl_pct this cycle
        return max(self.results, key=lambda r: r.pnl_pct).strategy_id

    @property
    def pool_pnl_pct(self) -> float:
        # (total_budget_after - total_budget_before) / total_budget_before
        if self.total_budget_before == 0:
            return 0.0
        return (self.total_budget_after - self.total_budget_before) / self.total_budget_before


@dataclass
class SessionResult:
    n_cycles: int
    initial_budget: float
    final_budget: float
    total_return_pct: float          # (final - initial) / initial
    cycle_summaries: list[CycleSummary]
    final_allocations: dict[str, float]   # last cycle allocations
    winner: str                      # strategy_id with highest cumulative real pnl
```

## Task

### 1. Create `core/multi_agent/director.py`

```python
class Director:
    def __init__(
        self,
        total_budget: float,
        workers: list[WorkerAgent],
        min_budget_fraction: float = 0.05,  # workers below 5% of pool go virtual
        exploration_coeff: float = 1.0,
        max_tune_workers: int = 4,           # ThreadPoolExecutor max_workers for tuning
        max_eval_workers: int = 4,           # ThreadPoolExecutor max_workers for eval
    ) -> None: ...
```

**`run_session(all_prices, cycle_size, lookback_size, n_tune_candidates=8) -> SessionResult`**

Runs the full session across all available cycles:
```
n_cycles = (len(all_prices) - lookback_size) // cycle_size
```
If `n_cycles < 1`, raise `ValueError("not enough prices for even one cycle")`.

Workers tune and eval are dispatched via `concurrent.futures.ThreadPoolExecutor`
(not ProcessPoolExecutor — workers share in-memory state).

**`_allocate() -> dict[str, float]`** — private method

Returns `{strategy_id: budget}` for all workers based on UCB1 scores.
Workers below `min_budget_fraction * total_budget` receive `0`.

**`_observe(strategy_id, pnl_pct) -> None`** — private method

Updates internal UCB1 state: increments `obs_count[strategy_id]` and accumulates
`sum_pnl_pct[strategy_id]`.

### 2. Write unit tests in `tests/unit/test_director.py`

```python
def test_equal_allocation_on_first_cycle():
    # Before any observations, UCB1 = inf for all workers
    # All workers must receive equal budget (total / n_workers)

def test_virtual_workers_excluded_from_pool_pnl():
    # A worker that gets budget=0 contributes virtual pnl
    # total_budget must NOT change based on virtual pnl

def test_real_pnl_updates_total_budget():
    # A real worker's pnl_pct=0.1 → total_budget increases by 10% of its allocation

def test_poor_performer_gets_virtual_after_many_cycles():
    # Repeatedly observe one worker with pnl_pct=-0.5
    # After enough cycles its UCB1 score drops below min_budget_fraction threshold
    # and it receives budget=0

def test_session_runs_correct_number_of_cycles():
    # 200 prices, cycle_size=48, lookback_size=100 → (200-100)//48 = 2 cycles

def test_session_result_final_budget_consistent():
    # SessionResult.final_budget == initial_budget + sum of all real pnl across cycles
```

### 3. Write integration test in `tests/integration/test_multi_agent_session.py`

```python
def test_three_worker_session_runs_end_to_end(tmp_path):
    # Create 3 WorkerAgents (ma_crossover_v1, rsi_v1, macd_v1) with genetic optimizer
    # Create Director with total_budget=30_000
    # Load btc_usdt_30m.csv — if missing, use btc_usdt_1d.csv as fallback
    # Run session with cycle_size=48, lookback_size=200
    # Assert: SessionResult.n_cycles >= 1
    # Assert: SessionResult.final_budget > 0
    # Assert: at least one CycleSummary has a non-zero real worker result
    # Assert: cycle_summaries[0].allocations sums to approximately total_budget
    #         (sum of non-virtual allocations + virtual = total)

def test_session_is_deterministic():
    # Run same session twice with same seed → identical cycle_summaries
```

## Acceptance Criteria

- [ ] `core/multi_agent/director.py` exists with `CycleSummary`, `SessionResult`, `Director`
- [ ] UCB1 allocation: equal split on first cycle, exploit/explore thereafter
- [ ] Workers below `min_budget_fraction` receive `budget=0` (virtual mode)
- [ ] Virtual P&L does not affect `total_budget`
- [ ] Real P&L accrues to `total_budget` each cycle
- [ ] Session runs correct number of cycles: `(len(prices) - lookback) // cycle_size`
- [ ] `uv run pytest tests/unit/test_director.py` green
- [ ] `uv run pytest tests/integration/test_multi_agent_session.py` green
- [ ] `uv run pytest` fully green

## Files to Create

- `core/multi_agent/director.py`
- `tests/unit/test_director.py`
- `tests/integration/test_multi_agent_session.py`

## Files to NOT Touch

- `core/multi_agent/worker_agent.py`
- `domains/`
- `meta/`
- `core/orchestration/`
- Any spec files
