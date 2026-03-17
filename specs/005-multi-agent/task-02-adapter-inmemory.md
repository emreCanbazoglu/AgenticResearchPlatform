# Task 02 — TradingAdapter In-Memory Price Interface

## Status
Pending

## Owner
Codex agent

## Context

`TradingAdapter.run()` currently accepts a `dataset_id` file path, loads the CSV,
optionally splits into train/test, then runs the backtest. For the multi-agent
session, WorkerAgent manages its own time windows and passes pre-sliced price
lists directly — no file I/O needed in the hot path.

We need a new method that accepts an in-memory `list[float]` of close prices and
runs the full backtest + scoring pipeline on it, without any train/test split
(the caller is responsible for windowing).

## Task

### 1. Add `run_on_prices()` to `TradingAdapter` in `domains/trading/adapter.py`

```python
def run_on_prices(
    self,
    *,
    prices: list[float],
    strategy_id: str,
    parameters: dict[str, float],
    seed: int,
) -> DomainRunResult:
```

**Behaviour:**
- Identical to `run()` except it takes `prices: list[float]` instead of
  `dataset_id: str`.
- Does NOT apply the `train_ratio` split. All prices are used for both
  running and scoring. (The caller manages windowing.)
- Raises `ValueError("prices list needs at least 20 rows")` if
  `len(prices) < 20`.
- All other validation, commission, metrics, and scoring logic is unchanged.

**Implementation note:** Refactor the shared computation into a private
`_run_on_price_list(prices, strategy_id, parameters)` helper so that both
`run()` and `run_on_prices()` call it — do NOT duplicate logic.

The refactoring should look like:

```python
def run(self, *, dataset_id, strategy_id, parameters, seed) -> DomainRunResult:
    prices = self._load_close_prices(dataset_id)
    split_idx = max(1, int(len(prices) * self.train_ratio))
    train_prices = prices[:split_idx]
    test_prices = prices[split_idx:] if self.train_ratio < 1.0 else prices
    # ... validation ...
    train_metrics = self._run_on_price_list(train_prices, strategy_id, parameters)
    test_metrics  = self._run_on_price_list(test_prices,  strategy_id, parameters)
    ...

def run_on_prices(self, *, prices, strategy_id, parameters, seed) -> DomainRunResult:
    if len(prices) < 20:
        raise ValueError("prices list needs at least 20 rows")
    metrics = self._run_on_price_list(prices, strategy_id, parameters)
    score   = self._compute_score(metrics)
    return DomainRunResult(metrics=metrics, score=score, artifacts={})

def _run_on_price_list(
    self,
    prices: list[float],
    strategy_id: str,
    parameters: dict[str, float],
) -> dict[str, float]:
    runner = STRATEGY_REGISTRY.get(strategy_id)
    if runner is None:
        raise ValueError(f"unsupported strategy_id: {strategy_id}")
    strategy_parameters = {
        "_initial_capital": self.initial_capital,
        "commission_rate": self.commission_rate,
        **parameters,
    }
    final_equity, trade_count, equity_curve, trade_pnls, commission_paid = runner(
        prices, strategy_parameters
    )
    equity_returns = [
        (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
        for i in range(1, len(equity_curve))
        if equity_curve[i-1] != 0
    ]
    total_return = profitability_score(self.initial_capital, final_equity)
    return {
        "initial_equity": float(self.initial_capital),
        "final_equity":   float(final_equity),
        "total_return":   float(total_return),
        "trade_count":    float(trade_count),
        "commission_paid": float(commission_paid),
        "max_drawdown":   float(max_drawdown(equity_curve)),
        "annualized_volatility": float(annualized_volatility(equity_returns)),
        "sharpe_ratio":   float(sharpe_ratio(equity_returns)),
        "win_rate":       float(win_rate(trade_pnls)),
    }
```

### 2. Write unit tests in `tests/unit/test_adapter_inmemory.py`

```python
def test_run_on_prices_matches_run_with_full_dataset(tmp_path):
    # Write same prices to a CSV; run() with train_ratio=1.0 and run_on_prices()
    # must return identical metrics and score

def test_run_on_prices_rejects_short_list():
    # len(prices) < 20 → ValueError

def test_run_on_prices_does_not_split():
    # With 100 prices, run_on_prices returns metrics for all 100
    # (trade_count and equity match a manual backtest on the full list)

def test_run_and_run_on_prices_share_same_logic(tmp_path):
    # run(train_ratio=1.0) and run_on_prices() on the same price list
    # must return identical DomainRunResult.metrics values
```

## Acceptance Criteria

- [ ] `TradingAdapter.run_on_prices(prices=..., strategy_id=..., parameters=..., seed=...)` exists
- [ ] `run()` and `run_on_prices()` both delegate to `_run_on_price_list()`
- [ ] No logic duplication between `run()` and `run_on_prices()`
- [ ] `run_on_prices()` raises `ValueError` for < 20 rows
- [ ] `run_on_prices()` does not apply train/test split
- [ ] All existing tests still pass (no regression)
- [ ] `uv run pytest tests/unit/test_adapter_inmemory.py` green
- [ ] `uv run pytest` fully green

## Files to Create

- `tests/unit/test_adapter_inmemory.py`

## Files to Modify

- `domains/trading/adapter.py` (add `run_on_prices`, refactor into `_run_on_price_list`)

## Files to NOT Touch

- `meta/`
- `core/`
- `scoring/`
- Any spec files
