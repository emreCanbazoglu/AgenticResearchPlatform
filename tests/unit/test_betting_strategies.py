from __future__ import annotations

import pytest

from domains.polymarket.base import BetAction, MarketSnapshot
from domains.polymarket.strategies.longshot_fade import LongshotFadeStrategy
from domains.polymarket.strategies.mean_reversion import MeanReversionStrategy
from domains.polymarket.strategies.momentum import MomentumStrategy


def _snapshot(
    *,
    current_price: float,
    price_history: list[float],
) -> MarketSnapshot:
    return MarketSnapshot(
        market_id="mkt-1",
        question="Will example event happen?",
        category="politics",
        current_price=current_price,
        price_history=price_history,
        days_to_resolution=7.0,
        tags=["example"],
    )


def test_longshot_fade_bets_no_on_low_price() -> None:
    strategy = LongshotFadeStrategy()
    snapshot = _snapshot(current_price=0.05, price_history=[0.06, 0.05])

    decision = strategy.evaluate(snapshot, {"threshold_low": 15, "threshold_high": 85, "min_confidence": 10})

    assert decision.action == BetAction.BET_NO


def test_longshot_fade_passes_on_middle_price() -> None:
    strategy = LongshotFadeStrategy()
    snapshot = _snapshot(current_price=0.50, price_history=[0.49, 0.50])

    decision = strategy.evaluate(snapshot, strategy.default_parameters)

    assert decision.action == BetAction.PASS


def test_longshot_fade_bets_yes_on_high_price() -> None:
    strategy = LongshotFadeStrategy()
    snapshot = _snapshot(current_price=0.95, price_history=[0.90, 0.95])

    decision = strategy.evaluate(snapshot, {"threshold_low": 15, "threshold_high": 85, "min_confidence": 10})

    assert decision.action == BetAction.BET_YES


def test_momentum_passes_on_insufficient_history() -> None:
    strategy = MomentumStrategy()
    snapshot = _snapshot(current_price=0.45, price_history=[0.40, 0.41])

    decision = strategy.evaluate(snapshot, {"lookback_window": 3, "momentum_threshold": 2, "max_price": 80, "min_price": 10})

    assert decision.action == BetAction.PASS


def test_momentum_bets_yes_on_upward_move() -> None:
    strategy = MomentumStrategy()
    snapshot = _snapshot(current_price=0.52, price_history=[0.45, 0.48, 0.52])

    decision = strategy.evaluate(snapshot, {"lookback_window": 3, "momentum_threshold": 2, "max_price": 80, "min_price": 10})

    assert decision.action == BetAction.BET_YES


def test_momentum_passes_on_weak_move() -> None:
    strategy = MomentumStrategy()
    snapshot = _snapshot(current_price=0.51, price_history=[0.50, 0.505, 0.51])

    decision = strategy.evaluate(snapshot, {"lookback_window": 3, "momentum_threshold": 2, "max_price": 80, "min_price": 10})

    assert decision.action == BetAction.PASS


def test_mean_reversion_bets_no_on_high_deviation() -> None:
    strategy = MeanReversionStrategy()
    history = [0.40] * 20
    snapshot = _snapshot(current_price=0.70, price_history=history)

    decision = strategy.evaluate(
        snapshot,
        {"mean_window": 12, "deviation_threshold": 5, "reversion_strength": 50},
    )

    assert decision.action == BetAction.BET_NO


def test_mean_reversion_passes_on_short_history() -> None:
    strategy = MeanReversionStrategy()
    snapshot = _snapshot(current_price=0.60, price_history=[0.50] * 5)

    decision = strategy.evaluate(
        snapshot,
        {"mean_window": 12, "deviation_threshold": 5, "reversion_strength": 50},
    )

    assert decision.action == BetAction.PASS


@pytest.mark.parametrize(
    ("strategy", "snapshot", "parameters"),
    [
        (
            LongshotFadeStrategy(),
            _snapshot(current_price=0.99, price_history=[0.96, 0.98, 0.99]),
            {"threshold_low": 15, "threshold_high": 85, "min_confidence": 10},
        ),
        (
            MomentumStrategy(),
            _snapshot(current_price=0.85, price_history=[0.50, 0.70, 0.90]),
            {"lookback_window": 3, "momentum_threshold": 2, "max_price": 90, "min_price": 10},
        ),
        (
            MeanReversionStrategy(),
            _snapshot(current_price=0.95, price_history=[0.20] * 20),
            {"mean_window": 12, "deviation_threshold": 5, "reversion_strength": 20},
        ),
    ],
)
def test_all_strategies_return_valid_probability(
    strategy: object,
    snapshot: MarketSnapshot,
    parameters: dict[str, int],
) -> None:
    decision = strategy.evaluate(snapshot, parameters)

    assert 0.0 <= decision.estimated_probability <= 1.0


@pytest.mark.parametrize(
    ("strategy", "snapshot", "parameters"),
    [
        (
            LongshotFadeStrategy(),
            _snapshot(current_price=0.01, price_history=[0.02, 0.01]),
            {"threshold_low": 15, "threshold_high": 85, "min_confidence": 10},
        ),
        (
            MomentumStrategy(),
            _snapshot(current_price=0.10, price_history=[0.60, 0.30, 0.10]),
            {"lookback_window": 3, "momentum_threshold": 2, "max_price": 90, "min_price": 10},
        ),
        (
            MeanReversionStrategy(),
            _snapshot(current_price=0.05, price_history=[0.90] * 20),
            {"mean_window": 12, "deviation_threshold": 5, "reversion_strength": 80},
        ),
    ],
)
def test_all_strategies_confidence_in_range(
    strategy: object,
    snapshot: MarketSnapshot,
    parameters: dict[str, int],
) -> None:
    decision = strategy.evaluate(snapshot, parameters)

    assert 0.0 <= decision.confidence <= 1.0


@pytest.mark.parametrize(
    ("strategy", "snapshot", "parameters"),
    [
        (
            LongshotFadeStrategy(),
            _snapshot(current_price=0.50, price_history=[0.49, 0.50]),
            {"threshold_low": 15, "threshold_high": 85, "min_confidence": 10},
        ),
        (
            MomentumStrategy(),
            _snapshot(current_price=0.50, price_history=[0.50, 0.505, 0.51]),
            {"lookback_window": 3, "momentum_threshold": 2, "max_price": 80, "min_price": 10},
        ),
        (
            MeanReversionStrategy(),
            _snapshot(current_price=0.505, price_history=[0.50] * 20),
            {"mean_window": 12, "deviation_threshold": 5, "reversion_strength": 50},
        ),
    ],
)
def test_pass_has_zero_confidence(
    strategy: object,
    snapshot: MarketSnapshot,
    parameters: dict[str, int],
) -> None:
    decision = strategy.evaluate(snapshot, parameters)

    assert decision.action == BetAction.PASS
    assert decision.confidence == 0.0


@pytest.mark.parametrize(
    ("strategy", "snapshot", "parameters"),
    [
        (
            LongshotFadeStrategy(),
            _snapshot(current_price=0.95, price_history=[0.90, 0.95]),
            {"threshold_low": 15, "threshold_high": 85, "min_confidence": 10},
        ),
        (
            MomentumStrategy(),
            _snapshot(current_price=0.52, price_history=[0.45, 0.48, 0.52]),
            {"lookback_window": 3, "momentum_threshold": 2, "max_price": 80, "min_price": 10},
        ),
        (
            MeanReversionStrategy(),
            _snapshot(current_price=0.70, price_history=[0.40] * 20),
            {"mean_window": 12, "deviation_threshold": 5, "reversion_strength": 50},
        ),
    ],
)
def test_strategy_evaluate_is_deterministic(
    strategy: object,
    snapshot: MarketSnapshot,
    parameters: dict[str, int],
) -> None:
    first = strategy.evaluate(snapshot, parameters)
    second = strategy.evaluate(snapshot, parameters)

    assert first == second
