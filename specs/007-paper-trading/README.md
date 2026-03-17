# Spec 007 — Paper Trading Mode

## Goal

Run the multi-agent Director/Worker system on live market data with a real clock —
workers trade every 30 minutes using real BTC prices, but with virtual money.
No orders are placed on any exchange. This is the bridge between backtesting
and live trading.

## What Changes vs Backtesting

| Backtesting (`run_session.py`) | Paper trading (`run_paper.py`) |
|---|---|
| Static historical CSV | Live Binance API, rolling window |
| Runs all cycles at once | One cycle per 30-minute wall-clock tick |
| State lives in memory | State persisted to disk between wakeups |
| Deterministic | Real market — different each run |
| Instant | Runs indefinitely until Ctrl+C |

## Architecture

```
run_paper.py
│
├── On startup:
│   ├── Load PaperSession from checkpoint (or init fresh)
│   ├── Fetch last LOOKBACK_SIZE candles from Binance (warm-up history)
│   └── Print session header
│
├── Main loop (runs forever):
│   ├── Sleep until next 30-minute UTC boundary
│   ├── Fetch latest CYCLE_SIZE candles from Binance
│   ├── Execute one Director cycle (tune → allocate → eval)
│   ├── Print cycle report
│   ├── Save PaperSession checkpoint to disk
│   └── Loop
│
└── On Ctrl+C:
    ├── Print final summary
    └── Save final checkpoint
```

## Tasks

| # | Task | Depends on | Status |
|---|---|---|---|
| 01 | PaperSession — state persistence + live candle loader | — | Pending |
| 02 | `run_paper.py` — scheduler loop + output formatting | Task 01 | Pending |

## Definition of Done

- [ ] `core/multi_agent/paper_session.py` exists with `PaperSession` class
- [ ] `PaperSession.run_one_cycle()` fetches live data and executes one Director cycle
- [ ] State (workers + Director budget + history) persists to `paper_session.json` between runs
- [ ] `uv run python run_paper.py` starts, prints header, and waits for the next 30m boundary
- [ ] Ctrl+C exits cleanly with a summary
- [ ] `uv run pytest` fully green (paper trading tests use mocked time + mocked API)
