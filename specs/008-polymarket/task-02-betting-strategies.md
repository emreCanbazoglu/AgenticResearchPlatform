# Task 02 — BettingStrategy Interface + 3 Strategies

## Status
Pending

## Owner
Codex agent

## Depends On
Nothing — can run in parallel with Task 01

## Context

Polymarket strategies are fundamentally different from trading strategies.
A trading strategy watches OHLCV data and generates buy/sell orders.
A betting strategy watches a probability time series and decides whether the
current market price is mispriced relative to its own estimate.

The output is a `BetDecision`: bet YES, bet NO, or pass. Size is determined
by Kelly criterion in the adapter, not the strategy — the strategy only
provides a probability estimate and a confidence level.

## Data Structures

### `domains/polymarket/base.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any

class BetAction(Enum):
    BET_YES = "bet_yes"
    BET_NO  = "bet_no"
    PASS    = "pass"

@dataclass
class BetDecision:
    action: BetAction
    estimated_probability: float   # strategy's fair-value estimate (0.0–1.0)
    confidence: float              # 0.0–1.0; used to scale Kelly fraction
    reasoning: str = ""            # human-readable explanation (optional)

@dataclass
class MarketSnapshot:
    market_id: str
    question: str
    category: str
    current_price: float           # market's current implied probability
    price_history: list[float]     # recent prices, oldest first
    days_to_resolution: float      # estimated time remaining
    tags: list[str]

class BettingStrategy:
    """
    Base class for all Polymarket betting strategies.

    A strategy must be:
    - Stateless between markets (no shared state across evaluate() calls)
    - Deterministic given the same MarketSnapshot and parameters
    - Free of external API calls

    Parameters are passed as a flat dict and must be numeric (int or float)
    to be compatible with the optimizer search space.
    """

    def evaluate(
        self,
        snapshot: MarketSnapshot,
        parameters: dict[str, Any],
    ) -> BetDecision:
        """
        Evaluate one market and return a bet decision.

        Must return BetDecision(action=PASS) when the strategy has
        insufficient data or no view on the market.
        """
        raise NotImplementedError

    @property
    def default_parameters(self) -> dict[str, Any]:
        """Midpoint defaults for each parameter in the search space."""
        raise NotImplementedError

    @property
    def search_space(self) -> dict[str, tuple[int, int]]:
        """Parameter search space for the optimizer."""
        raise NotImplementedError
```

## Strategy 1: Longshot Fade (`longshot_fade_v1`)

### Rationale
The favourite-longshot bias is one of the most robust findings in prediction
market research. Bettors systematically overprice low-probability outcomes
(longshots). This strategy fades markets where the current price is below a
threshold, betting NO (i.e. the event is even less likely than the market thinks).

Symmetrically, it fades very high-probability markets by betting NO when the
price is above an upper threshold — capturing the mirror effect where
near-certain outcomes are slightly underpriced.

### Parameters
```
threshold_low  : int   [range 5–25]   fade YES markets priced below this % (bet NO)
threshold_high : int   [range 75–95]  fade NO markets priced above this % (bet NO)
min_confidence : int   [range 10–50]  minimum confidence to act (as percentage)
```

### Logic
```
price_pct = current_price * 100

if price_pct < threshold_low:
    estimated_prob = price_pct * 0.6      # assume market is 40% too generous
    confidence = (threshold_low - price_pct) / threshold_low
    if confidence * 100 >= min_confidence:
        return BetDecision(BET_NO, estimated_prob / 100, confidence)

elif price_pct > threshold_high:
    estimated_prob = price_pct * 1.1      # assume market is 10% too stingy
    confidence = (price_pct - threshold_high) / (100 - threshold_high)
    if confidence * 100 >= min_confidence:
        return BetDecision(BET_YES, estimated_prob / 100, confidence)

return BetDecision(PASS, current_price, 0.0)
```

## Strategy 2: Momentum (`momentum_v1`)

### Rationale
Prediction market prices exhibit short-term momentum: a price that has been
moving in one direction tends to continue for a few hours before reverting.
This strategy bets in the direction of recent price movement when it exceeds
a momentum threshold.

### Parameters
```
lookback_window  : int   [range 3–24]   number of recent price points to measure momentum
momentum_threshold: int  [range 2–15]   minimum price move (%) to trigger a bet
max_price        : int   [range 60–90]  only bet on markets below this price (avoid near-certainties)
min_price        : int   [range 10–40]  only bet on markets above this price (avoid extreme longshots)
```

### Logic
```
if len(price_history) < lookback_window:
    return BetDecision(PASS, ...)

recent = price_history[-lookback_window:]
move = (recent[-1] - recent[0]) * 100   # in percentage points

if abs(move) < momentum_threshold:
    return BetDecision(PASS, ...)

if not (min_price <= current_price * 100 <= max_price):
    return BetDecision(PASS, ...)

if move > 0:
    # Upward momentum — bet YES
    confidence = min(abs(move) / 30.0, 1.0)
    return BetDecision(BET_YES, current_price + 0.05, confidence)
else:
    # Downward momentum — bet NO
    confidence = min(abs(move) / 30.0, 1.0)
    return BetDecision(BET_NO, current_price - 0.05, confidence)
```

## Strategy 3: Mean Reversion (`mean_reversion_v1`)

### Rationale
Prices overreact to recent news. When a market price deviates significantly
from its historical mean over a medium-term window, it tends to revert.
This strategy bets against the recent move when the deviation is large enough.

### Parameters
```
mean_window      : int   [range 12–96]   price points for baseline mean calculation
deviation_threshold: int [range 5–25]    minimum deviation from mean (%) to act
reversion_strength: int  [range 20–80]   expected reversion as % of deviation
```

### Logic
```
if len(price_history) < mean_window:
    return BetDecision(PASS, ...)

baseline_mean = mean(price_history[-mean_window:])
deviation = (current_price - baseline_mean) * 100   # in percentage points

if abs(deviation) < deviation_threshold:
    return BetDecision(PASS, ...)

# Estimate fair value as partial reversion
reversion_fraction = reversion_strength / 100
estimated_prob = baseline_mean + (current_price - baseline_mean) * (1 - reversion_fraction)
confidence = min(abs(deviation) / 40.0, 1.0)

if deviation > 0:
    # Price ran up — bet NO (expect reversion down)
    return BetDecision(BET_NO, estimated_prob, confidence)
else:
    # Price ran down — bet YES (expect reversion up)
    return BetDecision(BET_YES, estimated_prob, confidence)
```

## Tests

### `tests/unit/test_betting_strategies.py`

```python
def test_longshot_fade_bets_no_on_low_price():
    # price=0.05, threshold_low=15 → BET_NO

def test_longshot_fade_passes_on_middle_price():
    # price=0.50 → PASS

def test_longshot_fade_bets_yes_on_high_price():
    # price=0.95, threshold_high=85 → BET_YES

def test_momentum_passes_on_insufficient_history():
    # price_history shorter than lookback_window → PASS

def test_momentum_bets_yes_on_upward_move():
    # history trending up, current in [min_price, max_price] range → BET_YES

def test_momentum_passes_on_weak_move():
    # move < threshold → PASS

def test_mean_reversion_bets_no_on_high_deviation():
    # price well above mean → BET_NO

def test_mean_reversion_passes_on_short_history():
    # len(history) < mean_window → PASS

def test_all_strategies_return_valid_probability():
    # estimated_probability always in [0.0, 1.0]

def test_all_strategies_confidence_in_range():
    # confidence always in [0.0, 1.0]

def test_pass_has_zero_confidence():
    # all PASS decisions have confidence == 0.0
```

## Acceptance Criteria

- [ ] `domains/polymarket/base.py` with `BetAction`, `BetDecision`, `MarketSnapshot`,
      `BettingStrategy` implemented
- [ ] `domains/polymarket/strategies/` with `longshot_fade_v1`, `momentum_v1`,
      `mean_reversion_v1` implemented
- [ ] Each strategy is stateless — calling `evaluate()` twice on identical input
      gives identical output
- [ ] All strategies return `PASS` when they have insufficient data
- [ ] `estimated_probability` is always in [0.0, 1.0]
- [ ] `confidence` is always in [0.0, 1.0]
- [ ] All unit tests green
- [ ] `uv run pytest` fully green

## Files to Create

- `domains/polymarket/base.py`
- `domains/polymarket/strategies/__init__.py`
- `domains/polymarket/strategies/longshot_fade.py`
- `domains/polymarket/strategies/momentum.py`
- `domains/polymarket/strategies/mean_reversion.py`
- `tests/unit/test_betting_strategies.py`

## Files to NOT Touch

- `domains/trading/`
- `core/`
- `meta/`
- Any existing spec files
