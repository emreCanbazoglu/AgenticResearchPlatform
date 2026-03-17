# Next Steps

Primary planning reference: `RESEARCH_PLATFORM_PLANNING.md`

## Done

1. ~~Define canonical `ExperimentJob` schema and state machine.~~ — Complete.
2. ~~Specify scheduler policies (priority, fairness, quotas, retry).~~ — Complete.
3. ~~Define domain adapter contracts.~~ — Complete.

## ~~Crypto Trading V1~~ — Complete ✓ (`specs/002-crypto-trading-v1/`)
## ~~Optimizer Quality~~ — Complete ✓ (`specs/003-optimizers/`) — TPE + UCB1; 51/51 tests
## ~~Real Data + Walk-Forward~~ — Complete ✓ (`specs/004-real-data-walkforward/`)
## ~~Multi-Agent Director/Worker~~ — Complete ✓ (`specs/005-multi-agent/`) — 71/71 tests

- Director (UCB1 budget allocation), WorkerAgent (self-tune + eval), 3 strategies
- `run_session.py` — full multi-agent backtest on BTC 30m data

## ~~Backtest Realism~~ — Complete ✓ (`specs/006-backtest-realism/`) — 82/82 tests

- Position sizing (95% of cash per trade) + slippage (5 bps per fill) in `_run_backtest()`
- `WorkerAgent` wired with `position_size_fraction` + `slippage_rate`; cost breakdown in `run_session.py`

## ~~Paper Trading~~ — Complete ✓ (`specs/007-paper-trading/`) — 90/90 tests

- `PaperSession` — live Binance candle fetch (stdlib urllib), atomic JSON checkpoint, resume from saved state
- `run_paper.py` — real-clock loop, sleeps to next 30m UTC boundary, `--dry-run` mode, Ctrl+C clean exit

---

## Active Plan

*No active spec. Choose next focus area from Deferred below.*

---

## Deferred

- **Game economy simulator** (`domains/game_economy/`) — after paper trading is proven
- **Distributed workers** — Phase 3, no timeline yet
- **Worker failure-mode runbook** (`docs/runbooks/`)
