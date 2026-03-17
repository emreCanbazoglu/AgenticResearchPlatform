# Spec 005 — Multi-Agent Director/Worker System

## Goal

Replace the single-strategy campaign loop with a multi-agent system where:
- A **Director** holds a shared capital pool and allocates budget across workers each cycle
- **WorkerAgents** each own one strategy and self-tune between cycles
- Workers with zero allocation still run simulations on virtual capital so they keep learning
- The whole system runs in backtesting mode against historical 30-minute candles

## Architecture

```
Director
├── total_budget: float           # real capital pool
├── workers: list[WorkerAgent]    # one per strategy (MA, RSI, MACD)
├── allocation: UCB1              # bandit policy — exploit winners, explore weak
│
│  Cycle N:
│  ├── workers self-tune on lookback window (optimizer loop, no money)
│  ├── director allocates budget via UCB1 scores
│  ├── workers run eval on next window (real or virtual)
│  ├── real workers: P&L flows back into total_budget
│  ├── director observes P&L%, updates UCB1 state
│  └── Cycle N+1
│
└── SessionResult: per-cycle summary, final equity, winner strategy
```

## Tasks

| # | Task | Depends on | Status |
|---|---|---|---|
| 01 | Fetch 30m OHLCV data | — | Pending |
| 02 | TradingAdapter in-memory price interface | — | Pending |
| 03 | WorkerAgent | Task 02 | Pending |
| 04 | Director + budget allocation | Task 03 | Pending |
| 05 | Session runner + integration tests | Task 04 | Pending |

Tasks 01 and 02 are independent and dispatched in parallel.
Tasks 03 → 04 → 05 are sequential.

## Definition of Done

- [ ] `data/trading/btc_usdt_30m.csv` exists with ≥ 500 rows
- [ ] `TradingAdapter.run_on_prices()` accepts in-memory price list
- [ ] `WorkerAgent` self-tunes and runs eval with given budget
- [ ] `Director` allocates budget via UCB1 and runs full session
- [ ] Zero-budget workers run on virtual capital, still report scores
- [ ] `uv run python run_session.py` runs a full session and prints cycle-by-cycle report
- [ ] `uv run pytest` passes all tests
