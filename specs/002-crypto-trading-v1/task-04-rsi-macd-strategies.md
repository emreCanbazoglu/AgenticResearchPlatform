# Task 04 — RSI and MACD Strategies

## Status
Pending

## Owner
Codex agent

## Context

The trading domain currently has only one strategy: `MovingAverageCrossover` (MA crossover). For meaningful strategy research, we need a broader set of signal generators. RSI and MACD are the two most standard next candidates — they capture momentum and trend in different ways and provide distinct search dimensions for the optimizer.

## Task

Implement two new strategy classes in `domains/trading/strategies/` and register them in `domains/trading/adapter.py`.

---

## Strategy 1: RSI (Relative Strength Index)

### File
`domains/trading/strategies/rsi.py`

### Class
```python
@dataclass
class RSIStrategy:
    period: int          # lookback window for RSI (default 14)
    overbought: float    # sell threshold (default 70.0)
    oversold: float      # buy threshold (default 30.0)
```

### Signal logic

RSI measures average gain vs average loss over `period` candles.

```
gains = [max(price[i] - price[i-1], 0) for i in last `period` candles]
losses = [max(price[i-1] - price[i], 0) for i in last `period` candles]
avg_gain = mean(gains)
avg_loss = mean(losses)
if avg_loss == 0: RS = 100.0, RSI = 100.0
else: RS = avg_gain / avg_loss; RSI = 100 - (100 / (1 + RS))
```

Signal:
- `signal(prices, idx) -> int`
- Returns `1` (buy) if RSI < `oversold`
- Returns `-1` (sell) if RSI > `overbought`
- Returns `0` otherwise
- Returns `0` if `idx < period`

### Parameters exposed to optimizer search

| Parameter | Type | Range hint |
|---|---|---|
| `period` | int | 7–30 |
| `overbought` | float | 60–80 |
| `oversold` | float | 20–40 |

---

## Strategy 2: MACD (Moving Average Convergence Divergence)

### File
`domains/trading/strategies/macd.py`

### Class
```python
@dataclass
class MACDStrategy:
    fast_period: int    # fast EMA window (default 12)
    slow_period: int    # slow EMA window (default 26)
    signal_period: int  # signal line EMA window (default 9)
```

### Signal logic

Use simple moving averages (SMA) for V1 — no EMA required (avoids state management).

```
fast_ma = mean(prices[idx-fast_period+1 : idx+1])
slow_ma = mean(prices[idx-slow_period+1 : idx+1])
macd_line = fast_ma - slow_ma

# Signal line = SMA of last `signal_period` MACD values
# Compute historical MACD values for indices [idx-signal_period : idx]
signal_line = mean of macd values over last signal_period candles
```

Signal:
- `signal(prices, idx) -> int`
- Returns `1` if `macd_line > signal_line` (bullish crossover)
- Returns `-1` if `macd_line < signal_line` (bearish crossover)
- Returns `0` if `idx < slow_period + signal_period`

### Parameters exposed to optimizer search

| Parameter | Type | Range hint |
|---|---|---|
| `fast_period` | int | 5–15 |
| `slow_period` | int | 15–40 |
| `signal_period` | int | 5–15 |

Constraint: `fast_period < slow_period` always. Adapter must validate this and raise `ValueError` if violated.

---

## Adapter Registration

Update `domains/trading/adapter.py` to support new `strategy_id` values:

```python
STRATEGY_REGISTRY = {
    "ma_crossover_v1": _run_ma_crossover,
    "rsi_v1": _run_rsi,
    "macd_v1": _run_macd,
}
```

Refactor `run()` to dispatch via registry. Each strategy handler receives `(prices, parameters)` and returns `(final_equity, trade_count, equity_curve, trade_pnls)`.

The adapter's `run()` signature does not change.

## Constraints

- No external dependencies — standard library only
- All strategies must be deterministic (no randomness)
- All strategies operate on `list[float]` of close prices only
- `signal()` method must match the exact signature: `def signal(self, prices: list[float], idx: int) -> int`

## Acceptance Criteria

- [ ] `RSIStrategy` class in `domains/trading/strategies/rsi.py`
- [ ] `MACDStrategy` class in `domains/trading/strategies/macd.py`
- [ ] Both strategies registered in adapter under `rsi_v1` and `macd_v1`
- [ ] Adapter raises `ValueError` for unknown `strategy_id`
- [ ] `macd_v1` raises `ValueError` if `fast_period >= slow_period`
- [ ] RSI returns 0 when `idx < period`
- [ ] MACD returns 0 when insufficient history
- [ ] `rsi_v1` and `macd_v1` campaigns run end-to-end via `run_campaign()` without errors
- [ ] Existing `ma_crossover_v1` tests still pass
- [ ] New test file: `tests/unit/test_strategies.py`
  - Test RSI signal on a known monotonically increasing price series (should trigger overbought)
  - Test RSI signal on a known monotonically decreasing price series (should trigger oversold)
  - Test MACD returns 0 for insufficient history
  - Test MACD fast/slow validation

## Files to Create

- `domains/trading/strategies/rsi.py`
- `domains/trading/strategies/macd.py`
- `tests/unit/test_strategies.py`

## Files to Modify

- `domains/trading/adapter.py`

## Files to NOT Touch

- `domains/base.py`
- `scoring/`
- `core/`
- `persistence/`
- `meta/`
