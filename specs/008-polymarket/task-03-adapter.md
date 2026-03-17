# Task 03 — PolymarketAdapter (Backtest Engine)

## Status
Pending

## Owner
Codex agent

## Depends On
- Task 01 — `HistoricalMarketStore` must exist
- Task 02 — `BettingStrategy` interface + strategies must exist

## Context

The `PolymarketAdapter` is the Polymarket equivalent of `TradingAdapter`.
It implements `EnvironmentAdapter` from `domains/base.py` so the existing
optimizer and Director/Worker machinery can drive it unchanged.

The key difference from trading: instead of simulating a continuous price
series with buy/sell orders, we simulate a **portfolio of discrete binary bets**
across multiple resolved markets. Each market is an independent trial with a
known outcome — the backtest simply replays those outcomes.

## Backtest Model

```
For each market in the evaluation set:
  1. Build MarketSnapshot from historical price series
  2. Call strategy.evaluate(snapshot, parameters) → BetDecision
  3. If action == PASS: skip (no capital deployed)
  4. If action == BET_YES or BET_NO:
     a. Kelly fraction: f = kelly(estimated_prob, current_price, confidence)
        capped at max_kelly_fraction (default 0.25)
     b. bet_amount = current_capital * f
     c. shares = bet_amount / current_price   (for YES bet)
        or shares = bet_amount / (1 - current_price)  (for NO bet)
     d. At resolution:
        - BET_YES + outcome=1.0 → profit = shares * (1 - current_price)
        - BET_YES + outcome=0.0 → loss   = -bet_amount
        - BET_NO  + outcome=0.0 → profit = shares * current_price
        - BET_NO  + outcome=1.0 → loss   = -bet_amount
     e. current_capital += profit_or_loss
     f. Record BetRecord

Return PolymarketRunResult with all metrics
```

### Kelly criterion implementation
```python
def kelly_fraction(
    estimated_prob: float,
    market_price: float,
    confidence: float,
    max_fraction: float = 0.25,
) -> float:
    """
    Full Kelly fraction scaled by strategy confidence.

    For a YES bet at price p, net odds b = (1-p)/p
    f* = (estimated_prob * b - (1 - estimated_prob)) / b
       = (estimated_prob - market_price) / (1 - market_price)

    For a NO bet at price p, net odds b = p/(1-p)
    f* = ((1-estimated_prob) - (1-market_price)) / (market_price/(1-market_price))
       = (market_price - estimated_prob) / market_price

    Fraction is then scaled by confidence and capped at max_fraction.
    Negative or zero fraction → PASS (no edge).
    """
```

## Data Structures

### `domains/polymarket/adapter.py`

```python
@dataclass
class BetRecord:
    market_id: str
    question: str
    category: str
    action: BetAction
    entry_price: float           # market price when bet was placed
    estimated_prob: float        # strategy's estimate
    bet_amount: float
    shares: float
    outcome: float               # 1.0 or 0.0 at resolution
    profit: float                # net profit/loss
    kelly_fraction: float

@dataclass
class PolymarketRunResult:
    final_equity: float
    initial_equity: float
    roi: float                   # (final - initial) / initial
    total_bets: int
    winning_bets: int
    win_rate: float
    total_profit: float
    avg_kelly_fraction: float
    bets_by_category: dict[str, int]    # how many bets per category
    profit_by_category: dict[str, float]
    bet_records: list[BetRecord]

@dataclass
class PolymarketAdapter:
    initial_capital: float = 10_000.0
    max_kelly_fraction: float = 0.25
    min_market_liquidity: float = 1_000.0   # skip markets below this $ volume
    categories: list[str] = field(default_factory=list)  # empty = all categories

    def run(
        self,
        *,
        markets: list[MarketRecord],
        store: HistoricalMarketStore,
        strategy_id: str,
        parameters: dict[str, Any],
    ) -> PolymarketRunResult:
        """
        Backtest one strategy on a list of resolved markets.
        Markets are processed in resolution order (oldest first).
        """

    def run_on_snapshots(
        self,
        *,
        snapshots: list[MarketSnapshot],
        outcomes: list[float],
        strategy_id: str,
        parameters: dict[str, Any],
    ) -> PolymarketRunResult:
        """
        In-memory version for use by WorkerAgent (no disk access).
        Caller provides pre-built snapshots and their outcomes.
        """
```

### Strategy registry

```python
# domains/polymarket/adapter.py

_STRATEGY_REGISTRY: dict[str, BettingStrategy] = {
    "longshot_fade_v1":  LongshotFadeStrategy(),
    "momentum_v1":       MomentumStrategy(),
    "mean_reversion_v1": MeanReversionStrategy(),
}

def get_strategy(strategy_id: str) -> BettingStrategy:
    if strategy_id not in _STRATEGY_REGISTRY:
        raise ValueError(f"unknown strategy: {strategy_id}")
    return _STRATEGY_REGISTRY[strategy_id]
```

### Registration in platform adapter registry

Add `"polymarket"` to `core/execution/adapters.py`:
```python
def get_adapter(domain: str):
    if domain == "trading":
        return TradingAdapter()
    if domain == "polymarket":
        return PolymarketAdapter()
    raise ValueError(f"unknown domain: {domain}")
```

## Scoring

Reuse the existing scoring engine (`scoring/metrics.py`) where possible.
Map Polymarket metrics to the standard composite score:

```
score = w_roi * normalized_roi
      + w_win_rate * normalized_win_rate
      - w_drawdown * normalized_drawdown
      + w_bet_count * normalized_bet_count
```

Add a `config/scoring_polymarket.yaml` with weights tuned for prediction markets:
```yaml
roi:       0.50   # primary signal
win_rate:  0.25   # consistency
drawdown:  0.15   # risk (max losing streak fraction)
bet_count: 0.10   # penalise strategies that never bet
```

## Tests

### `tests/unit/test_polymarket_adapter.py`

```python
def test_kelly_fraction_no_edge_returns_zero():
    # estimated_prob == market_price → kelly = 0 → no bet

def test_kelly_fraction_positive_edge_bet_yes():
    # estimated_prob=0.7, market_price=0.5 → positive fraction

def test_kelly_fraction_capped_at_max():
    # very large edge → capped at max_kelly_fraction

def test_run_on_snapshots_all_pass_returns_initial_equity():
    # strategy always returns PASS → final_equity == initial_capital

def test_run_on_snapshots_correct_win():
    # bet YES, outcome=1.0 → profit computed correctly

def test_run_on_snapshots_correct_loss():
    # bet YES, outcome=0.0 → loss == bet_amount

def test_run_on_snapshots_no_bet_bet_no_correct():
    # bet NO, outcome=0.0 → profit computed correctly

def test_run_processes_markets_oldest_first():
    # markets with different resolution dates processed in order

def test_category_filter_skips_other_categories():
    # adapter with categories=["elections"] skips sports markets

def test_win_rate_computed_correctly():
    # 3 wins out of 5 bets → win_rate == 0.6
```

### `tests/integration/test_polymarket_backtest.py`

```python
def test_full_backtest_on_sample_data():
    # Load sample dataset, run all 3 strategies, verify results are non-trivial
    # (at least one strategy places at least one bet, ROI is finite)

def test_determinism():
    # Same markets + same parameters → identical PolymarketRunResult
```

## Acceptance Criteria

- [ ] `domains/polymarket/adapter.py` implemented with `BetRecord`,
      `PolymarketRunResult`, `PolymarketAdapter`
- [ ] `kelly_fraction()` function implemented and tested
- [ ] `run_on_snapshots()` is the core backtest path (used by WorkerAgent)
- [ ] `run()` wraps `run_on_snapshots()` using `HistoricalMarketStore`
- [ ] All 3 strategies are callable through the adapter via `strategy_id`
- [ ] `"polymarket"` registered in `core/execution/adapters.py`
- [ ] `config/scoring_polymarket.yaml` created
- [ ] Backtest is deterministic (same input → same output)
- [ ] All unit + integration tests green
- [ ] `uv run pytest` fully green

## Files to Create

- `domains/polymarket/adapter.py`
- `config/scoring_polymarket.yaml`
- `tests/unit/test_polymarket_adapter.py`
- `tests/integration/test_polymarket_backtest.py`

## Files to Modify

- `core/execution/adapters.py` — add `"polymarket"` branch

## Files to NOT Touch

- `domains/trading/`
- `meta/`
- `core/orchestration/`
- Any existing spec files
