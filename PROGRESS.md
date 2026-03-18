# Polymarket Domain — Progress

_Last updated: 2026-03-18_

---

## What Was Built

The Polymarket domain is a fully implemented binary-prediction-market adapter on top of the existing Agentic Research Platform. It covers data ingestion, three betting strategies, a backtest engine, an optional LLM valuation layer, and a paper-trading session manager.

### Spec coverage (specs/008-polymarket/)

| Task | File | Status |
|---|---|---|
| Task 01 — Data pipeline | `task-01-data-pipeline.md` | ✅ Complete |
| Task 02 — Betting strategies | `task-02-betting-strategies.md` | ✅ Complete |
| Task 03 — Backtest adapter | `task-03-adapter.md` | ✅ Complete |
| Task 04 — LLM evaluator | `task-04-llm-evaluator.md` | ✅ Complete (stub — no API key wired) |
| Task 05 — Paper trading | `task-05-paper-trading.md` | ✅ Complete |
| Task 06 — Integration entry point | `task-06-integration.md` | ✅ Complete |

All 6 tasks were implemented by Codex agents and reviewed/merged.

---

## Module Map

```
domains/polymarket/
  __init__.py
  base.py               # BetAction, BetDecision, MarketSnapshot, BettingStrategy ABC
  adapter.py            # PolymarketAdapter, kelly_fraction(), BetRecord, PolymarketRunResult
  data_store.py         # HistoricalMarketStore, MarketRecord, PricePoint
  llm_evaluator.py      # LLMEvaluator (Claude Haiku), LLMEstimate, daily JSON cache
  paper_session.py      # PolymarketPaperSession, VirtualPosition, VirtualPortfolio
  worker.py             # PolymarketWorkerAgent
  strategies/
    longshot_fade.py    # Fade extreme probabilities (< 0.10 or > 0.90)
    momentum.py         # Bet in the direction of recent price drift
    mean_reversion.py   # Fade overreactions beyond a z-score threshold

scripts/
  fetch_polymarket_data.py   # Pulls resolved markets + price histories from Gamma/CLOB APIs

data/polymarket/
  markets.json               # 500 resolved markets (Feb–Jun 2025)
  price_histories/           # 150 CSV price-history files (one per market with history)
  sample/                    # Original 20-market sample dataset

run_polymarket.py            # Entry point (see CLI flags below)
config/scoring_polymarket.yaml
```

---

## CLI

```bash
# Offline backtest (uses data/polymarket/ by default)
uv run python run_polymarket.py --backtest --data-dir data/polymarket

# Dry-run one live cycle (reads live Gamma API, no bets saved)
uv run python run_polymarket.py --dry-run

# Start paper-trading loop
uv run python run_polymarket.py --paper

# Show current paper session status
uv run python run_polymarket.py --status

# Enable LLM layer in backtest (requires ANTHROPIC_API_KEY)
uv run python run_polymarket.py --backtest --llm --data-dir data/polymarket
```

---

## Data Pipeline

Fetch script: `scripts/fetch_polymarket_data.py`

- Pulls closed markets from the Gamma API (`gamma-api.polymarket.com/markets`)
- Retrieves 30-day price history per market from the CLOB API (`clob.polymarket.com/prices-history`)
  using the YES token (77-digit CLOB token ID, not the market integer ID)
- Supports `--from-date` / `--to-date` flags for date-range filtering via `end_date_min` / `end_date_max`
- Infers categories from `sportsMarketType` field + question-text keyword matching
- Currently fetched: **500 markets** (Feb–Jun 2025), **150 have usable price histories**

**Category breakdown of fetched dataset:**

| Category | Count |
|---|---|
| other | 371 |
| crypto | 60 |
| politics | 58 |
| economics | 11 |

The "other" bucket is predominantly short-duration sports prop bets (esports round results, tennis game scores) that closed in hours, not the long-horizon elections/macro markets that are most interesting for strategy evaluation.

---

## Backtest Results

Run against 150 markets with price histories (Feb–Jun 2025), starting capital $10,000:

```
Strategy             Bets   Win%    ROI     Avg Kelly
───────────────────────────────────────────────────────
longshot_fade_v1      145    93.8%  +284.2%      22.6%
momentum_v1             8    75.0%   +22.2%      11.3%
mean_reversion_v1       3     0.0%   -14.1%       4.8%
```

**By category (longshot_fade_v1):**

| Category | Bets | ROI |
|---|---|---|
| crypto | 6 | +21.5% |
| economics | 11 | +2.2% |
| politics | 35 | +89.1% |
| other | 93 | +171.3% |

**Notable bets:**
- Best: _"Will Russia capture territory in Dnipropetrovsk Oblast by May 31?"_ — +$2,042.86 (BET_NO @ 0.20)
- Worst: _"Will 50–100k federal employees accept the buyout?"_ — -$3,188.25 (BET_NO @ 0.26)

### ⚠️ Important caveats on results

The +284% ROI for `longshot_fade_v1` is **not reliable** and should not be trusted at face value:

1. **Dataset skew** — the 500 fetched markets are predominantly short-duration sports prop bets resolved with an overwhelming NO bias (sport round results where a heavy favourite wins). `longshot_fade_v1` bets NO on extreme longshots, so it wins trivially on this data.
2. **No transaction costs** — the CLOB charges ~2% fee on each leg; this is not modelled yet.
3. **No liquidity constraints** — Kelly fractions are applied as if unlimited liquidity exists at quoted prices.
4. **Price history gaps** — only 150 of 500 markets have recoverable CLOB history; the 350 with no history are excluded from backtests, which may introduce survivorship bias.
5. **Look-ahead on category** — `longshot_fade_v1` uses the market question text to infer category at evaluation time, which is fine, but the resolution outcome is trivially knowable for many sports bets.

To get meaningful results, the dataset needs rebalancing toward elections/macro/crypto markets from longer time horizons.

---

## Known Issues / Next Steps

### Data quality (highest priority)
- [ ] Re-fetch targeting **2024 US election period** (Oct–Nov 2024) and other major macro events; these require `--from-date 2024-10-01 --to-date 2024-12-31`
- [ ] Current fetch: `end_date_min` / `end_date_max` params work on Gamma API — just re-run the script with appropriate flags
- [ ] Explicitly filter out markets with resolution windows < 7 days during fetch to eliminate prop-bet noise
- [ ] Fix "other" category bucket — improve keyword classifier to distinguish sports, entertainment, science, etc.

### Strategy improvements
- [ ] Add transaction cost model (~2% round-trip CLOB fee) to `kelly_fraction()`
- [ ] Cap position size by estimated market liquidity (available from `liquidityNum` field in Gamma API)
- [ ] `mean_reversion_v1` is undertriggered (3 bets only) — review z-score threshold calibration
- [ ] Add a calibration check: compare `estimated_probability` to actual resolution rates by probability bucket

### LLM evaluator
- [ ] Wire `ANTHROPIC_API_KEY` env var — the module exists and is spec-complete but has never been run end-to-end
- [ ] Validate that `llm_prior` injection into Kelly sizing produces meaningful signal vs noise

### Paper trading
- [ ] `--paper` mode is implemented but untested against live Gamma API
- [ ] The live cycle reads current open markets; need to verify `fetch_live_markets()` in `worker.py` handles API auth correctly (Polymarket CLOB requires API key for order placement, not just price reads)

### Testing
- [ ] No unit tests exist for the Polymarket domain yet (144 passing tests are all for trading/core)
- [ ] Add tests for: `kelly_fraction()` edge cases, strategy `evaluate()` contracts, `HistoricalMarketStore` load/query, `VirtualPortfolio` accounting

---

## Test Suite

144 tests passing (trading domain + core infrastructure). Polymarket domain has no tests yet.

```
uv run pytest tests/ --tb=no
# 144 passed in 5.28s
```
