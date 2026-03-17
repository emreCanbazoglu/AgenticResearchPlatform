# Task 05 — Crypto Trading V1 Integration Test

## Status
Pending (depends on Tasks 01–04)

## Owner
Codex agent

## Context

Tasks 01–04 introduce real data, commission, risk metrics, and two new strategies. This task adds an end-to-end integration test that validates all components working together on real crypto data, and updates `run_mvp.py` to demonstrate the full crypto V1 stack.

## Task

### 1. Integration test: `tests/integration/test_crypto_trading_v1.py`

Write a single integration test that runs three campaigns — one per strategy — on BTC data and validates the full output.

```python
def test_crypto_v1_all_strategies():
    # Run one campaign per strategy on btc_usdt_1d.csv
    # Validate that each produces a valid CampaignRunOutput
    # Validate that risk metrics are present and in range
    # Validate determinism: run each campaign twice, assert identical fingerprints + scores
```

Specifically test:

- [ ] All three `strategy_id` values run without error: `ma_crossover_v1`, `rsi_v1`, `macd_v1`
- [ ] Each campaign's `best_score` is a finite float (not `-inf` or `nan`)
- [ ] Returned metrics include: `max_drawdown`, `sharpe_ratio`, `win_rate`, `annualized_volatility`
- [ ] `max_drawdown` is in range `[0.0, 1.0]`
- [ ] `win_rate` is in range `[0.0, 1.0]`
- [ ] Running the same campaign twice with same seed produces identical `snapshot_fingerprint` and `best_score`
- [ ] `commission_paid` is present and >= 0.0

Use `iterations=2`, `batch_size=4`, `seed=42`, and `dataset_id="data/trading/btc_usdt_1d.csv"`.
Use a temporary SQLite path (`tmp_path` fixture) so tests don't pollute `experiments.sqlite`.

### 2. Update `run_mvp.py`

Replace the demo campaign with one that showcases the crypto V1 stack:

```python
CampaignConfig(
    campaign_id="crypto-v1-btc-ma",
    domain="trading",
    dataset_id="data/trading/btc_usdt_1d.csv",
    strategy_id="ma_crossover_v1",
    iterations=3,
    batch_size=8,
    seed=7,
    db_path="experiments.sqlite",
    max_workers=4,
    search_space={"fast_window": (2, 12), "slow_window": (8, 30)},
    optimizer="genetic",
)
```

Also print the new metrics from `best_parameters`:
```
Best Score (composite):  ...
Max Drawdown:            ...
Sharpe Ratio:            ...
```

The metrics aren't directly available on `CampaignRunOutput` — just print what's available. Don't change `CampaignRunOutput` structure.

## Acceptance Criteria

- [ ] `tests/integration/test_crypto_trading_v1.py` exists and all assertions pass
- [ ] Test uses `tmp_path` — no side effects on `experiments.sqlite`
- [ ] Test runs in under 60 seconds
- [ ] `run_mvp.py` runs without error using `btc_usdt_1d.csv`
- [ ] `uv run pytest` passes all tests (new + existing)

## Files to Create

- `tests/integration/test_crypto_trading_v1.py`

## Files to Modify

- `run_mvp.py`

## Files to NOT Touch

- `core/`
- `persistence/`
- `meta/`
- `domains/base.py`
- Any spec files
