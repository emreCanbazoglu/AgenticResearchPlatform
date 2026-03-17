from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class BetAction(Enum):
    BET_YES = "bet_yes"
    BET_NO = "bet_no"
    PASS = "pass"


@dataclass
class BetDecision:
    action: BetAction
    estimated_probability: float
    confidence: float
    reasoning: str = ""


@dataclass
class MarketSnapshot:
    market_id: str
    question: str
    category: str
    current_price: float
    price_history: list[float]
    days_to_resolution: float
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
