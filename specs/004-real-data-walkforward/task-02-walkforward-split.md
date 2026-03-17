# Task 02 — Walk-Forward Split

## Status
Pending

## Owner
Codex agent

## Context

`domains/trading/adapter.py` currently runs the optimizer and computes metrics on the full price series. This means the optimizer can overfit to the exact data it's being evaluated on. Reported Sharpe ratios and drawdowns are in-sample statistics — they will be better than what the strategy would achieve on new data.

A walk-forward split fixes this:
- **Train split** (first 70% of rows): the optimizer tunes parameters on this portion
- **Test split** (last 30% of rows): final metrics are computed on this held-out portion

The optimizer never sees test data. Reported metrics reflect out-of-sample performance.

## Current adapter signature

```python
@dataclass
class TradingAdapter:
    initial_capital: float = 10_000.0
    commission_rate: float = 0.001

    def run(self, *, dataset_id, strategy_id, parameters, seed) -> DomainRunResult:
        prices = self._load_close_prices(dataset_id)
        # ... runs backtest on full prices ...
```

## Task

### 1. Add `train_ratio` to `TradingAdapter` in `domains/trading/adapter.py`

```python
@dataclass
class TradingAdapter:
    initial_capital: float = 10_000.0
    commission_rate: float = 0.001
    train_ratio: float = 1.0   # default: no split (backward-compatible)
```

Default is `1.0` (use full series) to keep all existing tests passing without modification.

### 2. Apply the split in `run()`

After loading prices, split:
```python
split_idx = max(1, int(len(prices) * self.train_ratio))
train_prices = prices[:split_idx]
test_prices = prices[split_idx:] if self.train_ratio < 1.0 else prices
```

- Run the backtest on `train_prices` to produce optimizer signal (the score)
- Run the backtest on `test_prices` to produce the final reported metrics
- If `train_ratio == 1.0`, `train_prices == test_prices == prices` — same behaviour as today

**The returned `DomainRunResult` must report test metrics and the train score:**
```python
return DomainRunResult(
    metrics=test_metrics,   # all 9 metrics computed on test split
    score=train_score,      # composite_score on TRAIN split (what optimizer sees)
    artifacts={"train_score": train_score, "test_score": test_score},
)
```

This means the optimizer tunes based on train performance but the user sees test performance.

### 3. Validation

If `train_ratio < 1.0`, enforce a minimum split size:
- `train_prices` must have at least 30 rows
- `test_prices` must have at least 10 rows
- Raise `ValueError` with a clear message if either constraint is violated

### 4. Update `run_mvp.py`

Set `train_ratio=0.7` on the `TradingAdapter` in the `CampaignConfig` context, or pass it through the adapter instantiation before running. The campaign config doesn't have a `train_ratio` field — the adapter is instantiated inside the campaign orchestration. Check how `TradingAdapter` is instantiated in `core/` and set `train_ratio=0.7` there, OR expose it as a `domain_config` parameter in the campaign. The simplest approach: update `run_mvp.py` to pass `train_ratio=0.7` wherever `TradingAdapter` is constructed.

**Note:** Do NOT change `CampaignConfig` or `core/` orchestration to add `train_ratio` — the simplest compliant approach is sufficient. Review how `TradingAdapter` is constructed before making this change.

### 5. Write unit tests in `tests/unit/test_walkforward_split.py`

```python
def test_default_train_ratio_uses_full_series(tmp_path):
    # train_ratio=1.0 (default) → same results as before this change
    # Compare adapter with train_ratio=1.0 vs adapter without specifying train_ratio

def test_train_ratio_splits_correctly(tmp_path):
    # With 100-row dataset and train_ratio=0.7:
    # - optimizer score is based on first 70 rows
    # - returned metrics are based on last 30 rows
    # Verify by checking that metrics match a backtest run on last 30 rows only

def test_minimum_split_size_enforced(tmp_path):
    # 20-row dataset + train_ratio=0.5 → ValueError (test split too small)

def test_metrics_keys_unchanged(tmp_path):
    # train_ratio=0.7 → returned metrics still contain all 9 keys:
    # initial_equity, final_equity, total_return, trade_count, commission_paid,
    # max_drawdown, annualized_volatility, sharpe_ratio, win_rate
```

## Acceptance Criteria

- [ ] `TradingAdapter` has `train_ratio: float = 1.0` field
- [ ] Default `train_ratio=1.0` produces identical results to the current implementation
- [ ] With `train_ratio=0.7`, optimizer score uses train split; returned metrics use test split
- [ ] Minimum split sizes enforced with clear `ValueError`
- [ ] All existing tests still pass (no changes to expected values)
- [ ] `tests/unit/test_walkforward_split.py` passes
- [ ] `uv run pytest` passes all tests

## Files to Create

- `tests/unit/test_walkforward_split.py`

## Files to Modify

- `domains/trading/adapter.py` (add `train_ratio`, update `run()`)
- `run_mvp.py` (set `train_ratio=0.7`)

## Files to NOT Touch

- `core/`
- `meta/`
- `persistence/`
- `scoring/`
- `domains/base.py`
- Any spec files
