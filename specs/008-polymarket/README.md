# Spec 008 — Polymarket Domain Adapter

## Goal

Add Polymarket prediction markets as a first-class domain in the research platform.
The adapter enables the existing optimizer/Director/Worker architecture to research,
backtest, and paper-trade strategies against real Polymarket event data.

## Why Polymarket

Unlike liquid crypto markets where edge is largely arbitraged out by algorithmic
traders, Polymarket competes against retail bettors who exhibit well-documented,
persistent behavioural biases:

- **Favourite-longshot bias** — low-probability outcomes are systematically overpriced
- **Recency bias** — prices overreact to recent news, then mean-revert
- **Slow price discovery** — information can take hours to be fully reflected in prices
- **Category clustering** — model quality varies by market type (elections vs crypto
  price markets vs sports)

These inefficiencies have a structural reason to persist: participants bet for
entertainment, not purely for profit.

## Architecture Overview

```
PolymarketAdapter (domains/polymarket/adapter.py)
├── fetch_markets()              # pull open/resolved markets from Polymarket API
├── fetch_price_history()        # time-series of probability for one market
├── resolve()                    # look up resolution outcome (1.0 or 0.0)
│
├── run(market_id, parameters)   # backtest one strategy on one market's history
└── run_on_markets(markets, ...) # batch backtest across a list of markets

PolymarketStrategy (domains/polymarket/strategies/)
├── base.py                      # BettingStrategy interface
├── longshot_fade.py             # fade extreme low-probability markets
├── momentum.py                  # bet in direction of recent price movement
└── mean_reversion.py            # fade recent overreactions

HistoricalMarketStore (domains/polymarket/data_store.py)
├── load(path)                   # load resolved markets from local JSON/CSV
├── get_price_series(market_id)  # probability time series
└── get_outcome(market_id)       # 1.0 or 0.0

LLMEvaluator (domains/polymarket/llm_evaluator.py)
├── estimate_probability(market)  # LLM-based fair-value estimate
└── flag_mispriced(markets)       # markets where model disagrees with price by > threshold
```

## Key Domain Concepts

### Market representation
A Polymarket market is a YES/NO binary contract. The price at any time is the
market's implied probability (0.0–1.0). At resolution, it pays $1.00 for YES
or $0.00 for NO.

```
P&L per share = outcome (1.0 or 0.0) - entry_price
```

### Strategy output
Unlike trading strategies that output buy/sell orders, a betting strategy outputs:
```
BetDecision:
  action: BET_YES | BET_NO | PASS
  size_fraction: float   # fraction of allocated budget to bet (0.0–1.0)
  confidence: float      # strategy's confidence in the bet (used for Kelly sizing)
```

### Kelly criterion sizing
Optimal bet size under uncertainty:
```
f* = (p * b - q) / b
where:
  p = estimated probability of winning
  q = 1 - p
  b = net odds (= (1 - price) / price for a YES bet)
```
Strategies output a raw `confidence` score; the adapter converts to Kelly fraction
capped at `max_kelly_fraction` (default 0.25) to avoid ruin.

### Walk-forward structure
Each "cycle" is one calendar day. The optimizer tunes on the last N resolved markets
(train set), then evaluates on currently open markets (eval set). This mirrors the
train/test split from the crypto adapter.

## Tasks

| # | Task | Depends on | Status |
|---|---|---|---|
| 01 | Historical market data pipeline | — | Pending |
| 02 | BettingStrategy interface + 3 strategies | — | Pending |
| 03 | PolymarketAdapter (backtest engine) | 01, 02 | Pending |
| 04 | LLM evaluator (probability estimation) | 03 | Pending |
| 05 | Paper trading mode (live Polymarket API) | 03 | Pending |
| 06 | Integration + run_polymarket.py | 04, 05 | Pending |

Tasks 01 and 02 are independent and can be dispatched in parallel.
Tasks 03 → 04 → 05 → 06 are sequential.
Task 04 (LLM evaluator) is optional for the first working version — the adapter
must function without it.

## Definition of Done

- [ ] All 6 tasks complete and merged
- [ ] `uv run pytest` passes with no failures
- [ ] `uv run python run_polymarket.py --backtest` runs a full backtest session
      and prints per-strategy P&L and ROI
- [ ] `uv run python run_polymarket.py --dry-run` fetches live markets and runs
      one cycle without placing any real bets
- [ ] `CLAUDE.md` implementation status table updated
- [ ] `NEXT_STEPS.md` updated
