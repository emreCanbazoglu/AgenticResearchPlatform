# Task 02 — Commission Model for Trading Adapter

## Status
Pending

## Owner
Codex agent

## Context

`domains/trading/adapter.py` currently executes trades with zero cost. In crypto markets, maker/taker fees are typically 0.1% per trade. Without modelling fees, strategies that over-trade will appear falsely profitable. This task adds a configurable commission model.

## Task

Modify `domains/trading/adapter.py` to deduct a commission on every trade (both buy and sell).

## Exact Behaviour

Commission is applied as a percentage of trade value at fill time:

```
# On BUY (entering position):
shares_bought = (cash * (1 - commission_rate)) / price
cash = 0.0

# On SELL (exiting position):
proceeds = position * price
commission_cost = proceeds * commission_rate
cash = proceeds - commission_cost
position = 0.0
```

`commission_rate` defaults to `0.001` (0.1%).

## Interface Change

Add `commission_rate: float = 0.001` to the `TradingAdapter` dataclass:

```python
@dataclass
class TradingAdapter:
    initial_capital: float = 10_000.0
    commission_rate: float = 0.001
```

The adapter's `run()` signature does not change. `commission_rate` can also be passed via `parameters` dict as `"commission_rate"` to allow optimizer search over it (optional override — if present in `parameters`, use it; otherwise use the dataclass default).

## Metrics

Add `"commission_paid"` to the returned metrics dict:

```python
metrics = {
    "initial_equity": ...,
    "final_equity": ...,
    "total_return": ...,
    "trade_count": ...,
    "commission_paid": total_commission,  # new
}
```

## Determinism

Commission must be applied identically given the same parameters and price series. No randomness introduced.

## Acceptance Criteria

- [ ] `TradingAdapter` has `commission_rate: float = 0.001`
- [ ] Commission deducted on both buy and sell
- [ ] `commission_paid` present in returned metrics
- [ ] A strategy with 0 trades produces `commission_paid == 0.0`
- [ ] A strategy with `commission_rate=0.0` produces same result as old code
- [ ] Existing tests still pass
- [ ] New unit test: `tests/unit/test_commission_model.py`
  - Verify commission deducted correctly on a known 2-trade sequence
  - Verify `commission_rate=0.0` matches no-commission baseline
  - Verify `commission_paid` is present in metrics

## Files to Modify

- `domains/trading/adapter.py`

## Files to Create

- `tests/unit/test_commission_model.py`

## Files to NOT Touch

- `domains/base.py`
- `scoring/metrics.py`
- `core/`
- `persistence/`
- Any CSV data files
