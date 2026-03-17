# Task 06 — Integration + run_polymarket.py

## Status
Pending

## Owner
Codex agent

## Depends On
- Task 04 — LLM evaluator must exist
- Task 05 — Paper trading session must exist

## Context

Wire everything together into a single entry point (`run_polymarket.py`) and
write end-to-end integration tests. This is the equivalent of `run_session.py`
and `run_paper.py` for the Polymarket domain.

## Entry Point: `run_polymarket.py`

### Modes

```bash
# Backtest on sample historical data (offline, no API)
uv run python run_polymarket.py --backtest

# Backtest with LLM evaluation layer
uv run python run_polymarket.py --backtest --llm

# Paper trading dry-run (fetch live markets, evaluate, print — no bets)
uv run python run_polymarket.py --dry-run

# Start live paper trading loop (daily cycle, saves checkpoint)
uv run python run_polymarket.py --paper

# Show summary of current paper session
uv run python run_polymarket.py --status
```

### Backtest output
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POLYMARKET BACKTEST — 147 resolved markets (Jan 2025 – Mar 2026)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Strategy           Bets   Win%    ROI     Avg Kelly
  ─────────────────────────────────────────────────────
  longshot_fade_v1    34    61.8%  +8.4%     12.3%
  momentum_v1         22    45.5%  -2.1%      9.1%
  mean_reversion_v1   41    53.7%  +3.2%     11.8%

  By category (longshot_fade_v1):
    elections    :  12 bets  +14.2%
    crypto       :   8 bets   +3.1%
    sports       :  14 bets   +5.8%

  Best single bet: "Will Fed raise rates in March?" — +$312 (BET_NO @ 0.72)
  Worst single bet: "Will BTC hit $100k by Feb?" — -$180 (BET_YES @ 0.48)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Paper trading cycle output
```
Cycle 7  [2026-03-17]  │  Cash: $9,840  │  Open positions: 4  │  Resolved today: 2
  Resolved:
    [WIN ] "Will Macron resign before April?" — BET_NO @ 0.12 → +$98.40
    [LOSS] "BTC above $90k by Mar 15?"      — BET_YES @ 0.61 → -$120.00
  New bets (longshot_fade_v1):
    BET_NO  "Will X candidate win primary?" @ 0.08  Kelly 18%  $176.00
  Skipped (all other strategies — PASS or insufficient edge)
  Next cycle in 23h 42m
```

## Director/Worker wiring for Polymarket

The existing `Director` and `WorkerAgent` are reused with one adaptation:
instead of passing a price list to `run_eval()`, the caller passes a list
of `MarketSnapshot` objects. This requires the `WorkerAgent` to accept an
abstract "evaluation set" rather than a price list.

Two options:
1. **Thin wrapper** — create `PolymarketWorkerAgent` subclassing `WorkerAgent`
   that overrides `run_eval()` to accept `list[MarketSnapshot]`
2. **Protocol approach** — make `WorkerAgent.run_eval()` accept `Any` and let
   the adapter type-check at runtime

**Decision: use option 1** — `PolymarketWorkerAgent` in
`domains/polymarket/worker.py`. This keeps the existing `WorkerAgent` clean
and makes the Polymarket-specific behaviour explicit.

```python
class PolymarketWorkerAgent:
    strategy_id: str
    optimizer: Optimizer
    seed: int
    virtual_budget: float = 10_000.0
    adapter: PolymarketAdapter = field(default_factory=PolymarketAdapter)

    def self_tune(
        self,
        training_markets: list[MarketSnapshot],
        training_outcomes: list[float],
        n_candidates: int = 8,
    ) -> None: ...

    def run_eval(
        self,
        eval_markets: list[MarketSnapshot],
        eval_outcomes: list[float],
        budget: float,
        cycle_idx: int,
    ) -> CycleResult: ...
```

## Integration Tests

### `tests/integration/test_polymarket_end_to_end.py`

```python
def test_backtest_runs_on_sample_data():
    # uv run python run_polymarket.py --backtest
    # → exits 0, prints output, ROI is a finite number

def test_all_strategies_place_at_least_one_bet():
    # Each strategy fires on at least 1 of the 20 sample markets

def test_determinism():
    # Run backtest twice → identical results

def test_dry_run_fetches_no_real_bets(monkeypatch):
    # --dry-run with mocked API → no VirtualPositions created

def test_checkpoint_resume_continues_from_last_cycle(tmp_path, monkeypatch):
    # Run 2 cycles, save, restore, run 1 more cycle
    # → cycle_count == 3
```

## Acceptance Criteria

- [ ] `run_polymarket.py` exists with `--backtest`, `--dry-run`, `--paper`,
      `--status`, `--llm` flags
- [ ] `--backtest` runs offline on sample data in < 10 seconds
- [ ] `--backtest` output includes per-strategy ROI and win rate
- [ ] `--backtest` output includes per-category breakdown
- [ ] `--dry-run` fetches live markets and prints decisions without saving
- [ ] `PolymarketWorkerAgent` implemented in `domains/polymarket/worker.py`
- [ ] Director wired to `PolymarketWorkerAgent` for budget allocation
- [ ] All integration tests green
- [ ] `uv run pytest` fully green
- [ ] `CLAUDE.md` implementation status table updated

## Files to Create

- `domains/polymarket/worker.py`
- `run_polymarket.py`
- `tests/integration/test_polymarket_end_to_end.py`

## Files to NOT Touch

- `domains/trading/`
- `core/orchestration/`
- `meta/`
- Any existing spec files
