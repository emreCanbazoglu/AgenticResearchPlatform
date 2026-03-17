# Task 01 — Position Sizing and Slippage in Core Engine

## Status
Pending

## Owner
Codex agent

## Context

`_run_backtest()` in `domains/trading/adapter.py` currently goes fully-invested
on every buy signal and applies zero slippage. Two new parameters make it realistic:

- `position_size_fraction` — fraction of available cash to deploy per buy (1.0 = all-in)
- `slippage_rate` — one-way market impact cost as a fraction of price per fill

The existing return signature `StrategyRunOutput = tuple[float, int, list[float], list[float], float]`
will grow by one element to include `slippage_paid`:
```python
StrategyRunOutput = tuple[float, int, list[float], list[float], float, float]
# (final_equity, trade_count, equity_curve, trade_pnls, total_commission, total_slippage)
```

**Critical constraint:** with `position_size_fraction=1.0` and `slippage_rate=0.0`
the output MUST be numerically identical to the current implementation. All existing
tests must pass without modification.

## Task

### 1. Modify `_run_backtest()` in `domains/trading/adapter.py`

New signature:
```python
def _run_backtest(
    *,
    prices: list[float],
    strategy: SignalStrategy,
    initial_capital: float,
    commission_rate: float = 0.0,
    position_size_fraction: float = 1.0,
    slippage_rate: float = 0.0,
) -> StrategyRunOutput:
```

New return type alias (update at module level):
```python
StrategyRunOutput = tuple[float, int, list[float], list[float], float, float]
# (final_equity, trade_count, equity_curve, trade_pnls, commission_paid, slippage_paid)
```

**Buy logic** (replaces the current buy block):
```python
if signal > 0 and position == 0.0:
    invest_amount = cash * position_size_fraction       # fraction of cash to deploy
    exec_price = price * (1.0 + slippage_rate)          # slippage raises buy price
    slippage_cost = invest_amount * slippage_rate        # slippage cost in cash terms
    commission_cost = invest_amount * commission_rate    # commission on invested amount
    cash_spent = invest_amount                           # cash actually removed
    units = (invest_amount - commission_cost - slippage_cost) / exec_price
    position = units
    cash -= cash_spent
    buy_cost = invest_amount                             # cost basis for PnL calc
    total_commission += commission_cost
    total_slippage += slippage_cost
    trade_count += 1
```

**Sell logic** (replaces the current sell block):
```python
elif signal < 0 and position > 0.0:
    exec_price = price * (1.0 - slippage_rate)          # slippage lowers sell price
    gross_proceeds = position * exec_price
    slippage_cost = position * price * slippage_rate    # slippage cost
    commission_cost = gross_proceeds * commission_rate
    net_proceeds = gross_proceeds - commission_cost
    total_commission += commission_cost
    total_slippage += slippage_cost
    cash += net_proceeds
    if buy_cost is not None:
        trade_pnls.append(net_proceeds - buy_cost)
    position = 0.0
    buy_cost = None
    trade_count += 1
```

**Equity curve** uses mid-price (no change needed):
```python
equity_curve.append(cash + position * price)
```

**Return:**
```python
return final_equity, trade_count, equity_curve, trade_pnls, total_commission, total_slippage
```

**Backward-compatibility check:** with `position_size_fraction=1.0` and `slippage_rate=0.0`:
- `invest_amount = cash * 1.0 = cash`
- `exec_price = price * 1.0 = price`
- `slippage_cost = 0.0`
- `units = (cash - commission_cost) / price` — same as before
- `cash -= cash` → `cash = 0.0` — same as before ✓

### 2. Update all callers of `_run_backtest()` in `adapter.py`

`_run_ma_crossover`, `_run_rsi`, `_run_macd` all call `_run_backtest()` and unpack
its return value. They must:
- Pass `position_size_fraction` and `slippage_rate` from their `parameters` dict
  (with defaults of `1.0` and `0.0` respectively)
- Unpack the new 6-tuple: `final_equity, trade_count, equity_curve, trade_pnls, commission, slippage`

```python
def _run_ma_crossover(prices, parameters):
    ...
    return _run_backtest(
        prices=prices,
        strategy=strategy,
        initial_capital=float(parameters.get("_initial_capital", 10_000.0)),
        commission_rate=float(parameters.get("commission_rate", 0.001)),
        position_size_fraction=float(parameters.get("position_size_fraction", 1.0)),
        slippage_rate=float(parameters.get("slippage_rate", 0.0)),
    )
```

Same pattern for `_run_rsi` and `_run_macd`.

### 3. Update `_run_on_price_list()` in `TradingAdapter`

Currently unpacks a 5-tuple. Update to 6-tuple and add `slippage_paid` to the
returned metrics dict:

```python
final_equity, trade_count, equity_curve, trade_pnls, commission_paid, slippage_paid = runner(
    prices, strategy_parameters
)
...
return {
    ...existing 9 keys...,
    "slippage_paid": float(slippage_paid),
}
```

### 4. Update `TradingAdapter` dataclass fields

Add two new fields with backward-compatible defaults:

```python
@dataclass
class TradingAdapter:
    initial_capital: float = 10_000.0
    commission_rate: float = 0.001
    train_ratio: float = 1.0
    position_size_fraction: float = 1.0   # NEW
    slippage_rate: float = 0.0            # NEW
```

Both new fields must be injected into `strategy_parameters` in `_run_on_price_list()`
(or wherever the parameters dict is assembled) so the runner functions can read them:

```python
strategy_parameters = {
    "_initial_capital": self.initial_capital,
    "commission_rate": self.commission_rate,
    "position_size_fraction": self.position_size_fraction,
    "slippage_rate": self.slippage_rate,
    **parameters,   # caller params can still override
}
```

### 5. Write unit tests in `tests/unit/test_backtest_realism.py`

```python
def test_default_params_match_old_behaviour(tmp_path):
    # TradingAdapter() with defaults must produce same final_equity as before
    # Compare against a hardcoded known value or against the old return path

def test_position_size_fraction_limits_investment():
    # fraction=0.5: only half of cash is invested per trade
    # After a buy, remaining cash > 0
    # After a sell, cash = (original/2 invested) * price_ratio + untouched half

def test_slippage_reduces_pnl():
    # Same strategy + params, slippage_rate=0.01 → lower final_equity than slippage_rate=0.0

def test_slippage_paid_in_metrics():
    # With slippage_rate=0.001 and at least one trade, metrics["slippage_paid"] > 0

def test_slippage_zero_by_default():
    # TradingAdapter().run_on_prices(...) → metrics["slippage_paid"] == 0.0

def test_fraction_one_slippage_zero_is_backward_compatible():
    # Results must match pre-006 exactly for all 3 strategies
    # Run with fraction=1.0, slippage=0.0, compare metrics to a baseline run
    # (use the same parameters and seed)
```

## Acceptance Criteria

- [ ] `_run_backtest()` has `position_size_fraction` and `slippage_rate` parameters
- [ ] Returns 6-tuple including `slippage_paid`
- [ ] `TradingAdapter` has `position_size_fraction: float = 1.0` and `slippage_rate: float = 0.0`
- [ ] `metrics` dict contains `slippage_paid` key
- [ ] All 71 existing tests pass unchanged
- [ ] `uv run pytest tests/unit/test_backtest_realism.py` green
- [ ] `uv run pytest` fully green

## Files to Modify

- `domains/trading/adapter.py`

## Files to Create

- `tests/unit/test_backtest_realism.py`

## Files to NOT Touch

- `meta/`
- `core/`
- `scoring/`
- Any spec files
