# Task 05 — Polymarket Paper Trading (Live API)

## Status
Pending

## Owner
Codex agent

## Depends On
- Task 03 — `PolymarketAdapter` must exist

## Context

Paper trading mode runs the system against live Polymarket markets using
real current data, but places no real bets. It is the Polymarket equivalent
of `PaperSession` from spec 007.

The key difference from crypto paper trading:
- Cycles are **daily** (not 30-minute) — market prices update continuously
  but meaningful new information arrives on a daily cadence
- Markets are **discrete events** that open and close — the system must
  manage an evolving set of open markets, not a single continuous price series
- Outcomes resolve asynchronously — a bet placed today might not resolve
  for weeks

## Polymarket Live API

```
Base URL: https://clob.polymarket.com

Endpoints used:
  GET /markets?active=true&limit=100        — fetch open markets
  GET /prices-history?market={id}&interval=1h — price history for one market
  GET /markets/{id}                          — single market details

Authentication: None required for read-only data
Rate limit: 10 requests/second
```

## Data Structures

```python
# domains/polymarket/paper_session.py

@dataclass
class PolymarketPaperConfig:
    categories: list[str] = field(default_factory=lambda: ["elections", "crypto", "sports"])
    max_open_markets: int = 50          # max markets to evaluate per cycle
    cycle_interval_hours: int = 24      # how often to run (default: daily)
    initial_capital: float = 10_000.0
    max_kelly_fraction: float = 0.25
    checkpoint_path: str = "paper_polymarket.json"
    use_llm: bool = False               # whether to call LLM evaluator

@dataclass
class VirtualPosition:
    market_id: str
    question: str
    action: BetAction
    entry_price: float
    bet_amount: float
    shares: float
    opened_at: datetime
    estimated_prob: float
    strategy_id: str

@dataclass
class VirtualPortfolio:
    cash: float                              # undeployed capital
    open_positions: list[VirtualPosition]    # bets awaiting resolution
    closed_positions: list[BetRecord]        # resolved bets
    total_profit: float

class PolymarketPaperSession:
    def run_one_cycle(self) -> CycleSummary: ...
    def save(self, path: str | None = None) -> None: ...
    @classmethod
    def load(cls, path: str, workers: list[WorkerAgent]) -> PolymarketPaperSession: ...
    def summary(self) -> dict: ...
```

## Cycle Logic

Each cycle:
```
1. FETCH OPEN MARKETS
   - GET /markets?active=true&limit=N
   - Filter by configured categories
   - Fetch price history for each

2. CHECK RESOLUTIONS
   - For each open virtual position, check if the market has resolved
   - If resolved: compute profit/loss, move to closed_positions
   - Update portfolio cash

3. TUNE WORKERS (on recently resolved markets as training data)
   - Collect markets resolved in the last N days as training set
   - Each worker runs self_tune() on these resolved markets

4. ALLOCATE BUDGET (UCB1 across workers/strategies)
   - Director allocates virtual capital across workers

5. EVALUATE OPEN MARKETS
   - Each worker evaluates all open markets with its current params
   - Collect BetDecision per (worker, market) pair

6. PLACE VIRTUAL BETS
   - For each BetDecision that is not PASS:
     - Compute Kelly fraction
     - Create VirtualPosition
     - Deduct from portfolio cash

7. LOG CYCLE SUMMARY
   - New bets placed, positions resolved, portfolio value

8. SAVE CHECKPOINT
```

## Tests

### `tests/unit/test_polymarket_paper_session.py`

```python
def test_resolution_check_closes_position(monkeypatch):
    # Market that resolved YES → open position closed, profit computed

def test_new_bets_deduct_from_cash(monkeypatch):
    # After cycle, portfolio.cash < initial_capital

def test_pass_decisions_create_no_positions(monkeypatch):
    # All strategies return PASS → no open positions created

def test_checkpoint_roundtrip(tmp_path, monkeypatch):
    # Save then load → identical session state

def test_load_from_missing_file_creates_fresh_session(tmp_path):
    # Non-existent checkpoint path → fresh session, no error
```

## Acceptance Criteria

- [ ] `domains/polymarket/paper_session.py` implemented
- [ ] `VirtualPosition` and `VirtualPortfolio` track paper bets correctly
- [ ] Resolution checking updates portfolio correctly
- [ ] Checkpoint save/load preserves full portfolio state
- [ ] `--dry-run` mode fetches live data but places no bets (just prints)
- [ ] Rate limiting respected (≤ 10 req/s to Polymarket API)
- [ ] All unit tests green (API calls mocked)
- [ ] `uv run pytest` fully green

## Files to Create

- `domains/polymarket/paper_session.py`
- `tests/unit/test_polymarket_paper_session.py`

## Files to NOT Touch

- `domains/trading/`
- `core/`
- `meta/`
- Any existing spec files
