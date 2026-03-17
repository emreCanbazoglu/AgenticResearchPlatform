# Spec 006 — Backtest Realism

## Goal

Make the simulation more faithful to real market conditions by adding two missing cost
components that currently cause the backtest to be overly optimistic:

1. **Position sizing** — instead of always going all-in, invest only a fraction of
   available cash per trade. This makes strategies more robust and prevents scenarios
   where a single bad trade wipes out the entire position.

2. **Slippage model** — every fill has a market-impact cost. On a buy the execution
   price is slightly higher than mid; on a sell it is slightly lower. Without this,
   high-frequency strategies appear better than they are.

Both are **additive costs** on top of the existing commission model. Both default to
values that reproduce current behaviour exactly (backward compatible).

## Realism Impact

| Before | After |
|---|---|
| Always fully invested | Invest `position_size_fraction` of cash (default 1.0 = same) |
| No slippage | 5 bps per side (default 0.0 = same) |
| Cost = commission only | Cost = commission + slippage per fill |
| PnL slightly inflated | PnL closer to real execution |

## Tasks

| # | Task | Depends on | Status |
|---|---|---|---|
| 01 | Position sizing + slippage in core engine | — | Pending |
| 02 | Surface new params in WorkerAgent + defaults in run_session.py | Task 01 | Pending |

## Definition of Done

- [ ] `_run_backtest()` accepts `position_size_fraction` and `slippage_rate`
- [ ] `TradingAdapter` has `position_size_fraction: float = 1.0` and `slippage_rate: float = 0.0`
- [ ] `WorkerAgent` passes both through to `TradingAdapter`
- [ ] `metrics` dict gains `slippage_paid` key
- [ ] Default values reproduce existing test results exactly (all 71 tests still pass)
- [ ] `run_session.py` uses realistic defaults: `position_size_fraction=0.95`, `slippage_rate=0.0005`
- [ ] `uv run pytest` green
