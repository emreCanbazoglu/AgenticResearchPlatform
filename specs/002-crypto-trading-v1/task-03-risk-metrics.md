# Task 03 — Full Risk Metrics + Scoring Config

## Status
Pending (depends on Task 02 for commission_paid metric, but can be implemented in parallel)

## Owner
Codex agent

## Context

`scoring/metrics.py` only contains `profitability_score()` (simple ROI). The `SCORING_SPEC.md` requires Sharpe ratio, max drawdown, volatility, win rate, and a composite score driven by configurable weights. This is especially important for crypto where high-return strategies often carry ruinous drawdowns.

## Task

### 1. Implement risk metrics in `scoring/metrics.py`

Add the following pure functions. All inputs are lists of floats. No external dependencies — standard library only.

#### `max_drawdown(equity_curve: list[float]) -> float`
- Returns the maximum peak-to-trough decline as a positive fraction (e.g. 0.35 = 35% drawdown)
- `equity_curve` is a list of equity values over time (e.g. `[10000, 10500, 9800, ...]`)
- If curve has fewer than 2 points, return 0.0
- Formula: `max over all i<j of (curve[i] - curve[j]) / curve[i]`

#### `annualized_volatility(daily_returns: list[float], periods_per_year: int = 365) -> float`
- `daily_returns`: list of fractional period returns (e.g. `[0.01, -0.02, 0.005, ...]`)
- Returns annualized standard deviation: `std(daily_returns) * sqrt(periods_per_year)`
- If fewer than 2 returns, return 0.0

#### `sharpe_ratio(daily_returns: list[float], risk_free_rate: float = 0.0, periods_per_year: int = 365) -> float`
- Returns annualized Sharpe: `(mean(daily_returns) - risk_free_rate/periods_per_year) / std(daily_returns) * sqrt(periods_per_year)`
- If std is 0 or fewer than 2 returns, return 0.0

#### `win_rate(trade_pnls: list[float]) -> float`
- `trade_pnls`: list of per-trade P&L values (positive = win, negative = loss)
- Returns fraction of winning trades: `wins / total`
- If empty list, return 0.0

#### `composite_score(metrics: dict[str, float], weights: dict[str, float]) -> float`
- Combines normalized metrics into a single scalar
- Formula: `weights["return"] * metrics["total_return"] + weights["sharpe"] * metrics["sharpe_ratio"] - weights["drawdown"] * metrics["max_drawdown"]`
- Missing keys in metrics treated as 0.0
- Does not normalize — normalization is the caller's responsibility in V1

### 2. Update `domains/trading/adapter.py` to compute and return all metrics

The adapter must now compute and return the full metric set. This requires tracking the equity curve and trade P&Ls during simulation.

**Equity curve**: append `cash + position * price` after each candle.

**Trade P&Ls**: on each SELL, record `(sell_proceeds - buy_cost)` as a trade P&L entry.

Updated `metrics` dict returned by `run()`:

```python
metrics = {
    "initial_equity": float,
    "final_equity": float,
    "total_return": float,          # (final - initial) / initial
    "trade_count": float,
    "commission_paid": float,       # from Task 02 (default 0.0 if not yet done)
    "max_drawdown": float,          # from equity_curve
    "annualized_volatility": float, # from daily equity returns
    "sharpe_ratio": float,          # from daily equity returns
    "win_rate": float,              # from trade_pnls
}
```

**Score** returned by `run()` must use `composite_score()` with weights loaded from `config/scoring.yaml`. If the file doesn't exist, fall back to hardcoded defaults (see below).

### 3. Create `config/scoring.yaml`

```yaml
# Scoring weights for composite score.
# Score = return_weight * total_return
#       + sharpe_weight * sharpe_ratio
#       - drawdown_weight * max_drawdown
# Crypto profile: heavy drawdown penalty.
return_weight: 0.4
sharpe_weight: 0.4
drawdown_weight: 0.2
```

Load this file in `scoring/metrics.py` using only the standard library (`tomllib` is not available — use a simple YAML parser or just `re`-based key:value reader since the format is flat). Alternatively, use `pathlib` + manual line parsing. No `pyyaml` dependency.

**Config loading**: implement `load_scoring_weights(path: str = "config/scoring.yaml") -> dict[str, float]`. Cache result in a module-level dict after first load. If file not found, return hardcoded defaults:

```python
DEFAULT_WEIGHTS = {"return_weight": 0.4, "sharpe_weight": 0.4, "drawdown_weight": 0.2}
```

## Acceptance Criteria

- [ ] All 5 new functions present in `scoring/metrics.py` with correct signatures
- [ ] `max_drawdown([10000, 10000])` returns `0.0`
- [ ] `max_drawdown([10000, 8000, 9000])` returns `0.2` (20% drawdown from 10000 to 8000)
- [ ] `win_rate([])` returns `0.0`
- [ ] `sharpe_ratio([0.01] * 10)` returns a positive float
- [ ] `sharpe_ratio([0.0] * 10)` returns `0.0`
- [ ] `config/scoring.yaml` exists and is valid
- [ ] `load_scoring_weights()` returns correct weights from file
- [ ] `load_scoring_weights("nonexistent.yaml")` returns DEFAULT_WEIGHTS without raising
- [ ] Adapter's `run()` returns all 9 metrics listed above
- [ ] Adapter's `run()` score uses `composite_score()` with loaded weights
- [ ] Existing tests still pass
- [ ] New unit test file: `tests/unit/test_risk_metrics.py`
  - Test each function with known inputs and expected outputs
  - Test `load_scoring_weights` with missing file

## Files to Modify

- `scoring/metrics.py`
- `domains/trading/adapter.py`

## Files to Create

- `config/scoring.yaml`
- `tests/unit/test_risk_metrics.py`

## Files to NOT Touch

- `domains/base.py`
- `core/`
- `persistence/`
- `meta/`
