# Spec 002 — Crypto Trading V1

## Goal

Upgrade the trading domain from a synthetic smoke-test stub into a functional crypto strategy research environment.

## Scope

Real historical-style data (BTC/ETH), commission model, full risk metrics, two new strategies (RSI, MACD), and an end-to-end integration test.

## Tasks

| # | Task | Depends on | Status |
|---|---|---|---|
| 01 | BTC/ETH historical OHLCV data | — | Pending |
| 02 | Commission model | — | Pending |
| 03 | Full risk metrics + scoring config | — | Pending |
| 04 | RSI and MACD strategies | — | Pending |
| 05 | Integration test + run_mvp update | 01, 02, 03, 04 | Pending |

Tasks 01–04 are independent and can be dispatched to Codex agents in parallel.
Task 05 must run after all others are merged.

## Definition of Done

- [ ] All 5 tasks complete and merged
- [ ] `uv run pytest` passes with no failures
- [ ] `uv run python run_mvp.py` runs on `btc_usdt_1d.csv` and prints composite score
- [ ] `CLAUDE.md` implementation status table updated
- [ ] `NEXT_STEPS.md` updated to mark crypto V1 complete
