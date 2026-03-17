from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from domains.polymarket.adapter import PolymarketAdapter, _STRATEGY_REGISTRY, kelly_fraction
from domains.polymarket.base import BetAction, BetDecision, BettingStrategy, MarketSnapshot
from domains.polymarket.data_store import MarketRecord, PricePoint


@dataclass
class _FixedDecisionStrategy(BettingStrategy):
    decision: BetDecision

    def evaluate(self, snapshot: MarketSnapshot, parameters: dict[str, float]) -> BetDecision:
        del snapshot, parameters
        return self.decision

    @property
    def default_parameters(self) -> dict[str, float]:
        return {}

    @property
    def search_space(self) -> dict[str, tuple[int, int]]:
        return {}


@dataclass
class _RecordingStrategy(BettingStrategy):
    order: list[str]

    def evaluate(self, snapshot: MarketSnapshot, parameters: dict[str, float]) -> BetDecision:
        del parameters
        self.order.append(snapshot.market_id)
        return BetDecision(
            action=BetAction.PASS,
            estimated_probability=snapshot.current_price,
            confidence=0.0,
        )

    @property
    def default_parameters(self) -> dict[str, float]:
        return {}

    @property
    def search_space(self) -> dict[str, tuple[int, int]]:
        return {}


class _FakeStore:
    def __init__(self, series_by_market_id: dict[str, list[PricePoint]]) -> None:
        self.series_by_market_id = series_by_market_id

    def get_price_series(self, market_id: str) -> list[PricePoint]:
        return list(self.series_by_market_id.get(market_id, []))


def _snapshot(category: str = "elections", price: float = 0.5, market_id: str = "mkt") -> MarketSnapshot:
    return MarketSnapshot(
        market_id=market_id,
        question="Will event happen?",
        category=category,
        current_price=price,
        price_history=[price - 0.1, price],
        days_to_resolution=1.0,
        tags=["tag"],
    )


def _market(market_id: str, category: str, resolved_at: datetime) -> MarketRecord:
    created_at = resolved_at - timedelta(days=3)
    return MarketRecord(
        market_id=market_id,
        question=f"q-{market_id}",
        category=category,
        created_at=created_at,
        resolved_at=resolved_at,
        outcome=1.0,
        tags=["x"],
    )


def test_kelly_fraction_no_edge_returns_zero() -> None:
    assert kelly_fraction(estimated_prob=0.5, market_price=0.5, confidence=1.0) == pytest.approx(0.0)


def test_kelly_fraction_positive_edge_bet_yes() -> None:
    value = kelly_fraction(estimated_prob=0.7, market_price=0.5, confidence=1.0)
    assert value > 0.0


def test_kelly_fraction_capped_at_max() -> None:
    value = kelly_fraction(estimated_prob=0.99, market_price=0.01, confidence=1.0, max_fraction=0.25)
    assert value == pytest.approx(0.25)


def test_run_on_snapshots_all_pass_returns_initial_equity() -> None:
    strategy_id = "test_pass_strategy"
    _STRATEGY_REGISTRY[strategy_id] = _FixedDecisionStrategy(
        BetDecision(BetAction.PASS, estimated_probability=0.5, confidence=0.0)
    )
    try:
        adapter = PolymarketAdapter(initial_capital=10_000.0)
        result = adapter.run_on_snapshots(
            snapshots=[_snapshot(), _snapshot(market_id="mkt2")],
            outcomes=[1.0, 0.0],
            strategy_id=strategy_id,
            parameters={},
        )
    finally:
        del _STRATEGY_REGISTRY[strategy_id]

    assert result.final_equity == pytest.approx(10_000.0)
    assert result.total_bets == 0


def test_run_on_snapshots_correct_win() -> None:
    strategy_id = "test_yes_win"
    _STRATEGY_REGISTRY[strategy_id] = _FixedDecisionStrategy(
        BetDecision(BetAction.BET_YES, estimated_probability=0.7, confidence=1.0)
    )
    try:
        adapter = PolymarketAdapter(initial_capital=10_000.0, max_kelly_fraction=0.25)
        result = adapter.run_on_snapshots(
            snapshots=[_snapshot(price=0.5)],
            outcomes=[1.0],
            strategy_id=strategy_id,
            parameters={},
        )
    finally:
        del _STRATEGY_REGISTRY[strategy_id]

    expected_bet = 10_000.0 * 0.25
    expected_shares = expected_bet / 0.5
    expected_profit = expected_shares * (1.0 - 0.5)

    assert result.total_bets == 1
    assert result.bet_records[0].profit == pytest.approx(expected_profit)
    assert result.final_equity == pytest.approx(10_000.0 + expected_profit)


def test_run_on_snapshots_correct_loss() -> None:
    strategy_id = "test_yes_loss"
    _STRATEGY_REGISTRY[strategy_id] = _FixedDecisionStrategy(
        BetDecision(BetAction.BET_YES, estimated_probability=0.7, confidence=1.0)
    )
    try:
        adapter = PolymarketAdapter(initial_capital=10_000.0, max_kelly_fraction=0.25)
        result = adapter.run_on_snapshots(
            snapshots=[_snapshot(price=0.5)],
            outcomes=[0.0],
            strategy_id=strategy_id,
            parameters={},
        )
    finally:
        del _STRATEGY_REGISTRY[strategy_id]

    expected_bet = 10_000.0 * 0.25
    assert result.total_bets == 1
    assert result.bet_records[0].profit == pytest.approx(-expected_bet)
    assert result.final_equity == pytest.approx(10_000.0 - expected_bet)


def test_run_on_snapshots_no_bet_bet_no_correct() -> None:
    strategy_id = "test_no_win"
    _STRATEGY_REGISTRY[strategy_id] = _FixedDecisionStrategy(
        BetDecision(BetAction.BET_NO, estimated_probability=0.3, confidence=1.0)
    )
    try:
        adapter = PolymarketAdapter(initial_capital=10_000.0, max_kelly_fraction=0.25)
        result = adapter.run_on_snapshots(
            snapshots=[_snapshot(price=0.6)],
            outcomes=[0.0],
            strategy_id=strategy_id,
            parameters={},
        )
    finally:
        del _STRATEGY_REGISTRY[strategy_id]

    expected_bet = 10_000.0 * 0.25
    expected_shares = expected_bet / (1.0 - 0.6)
    expected_profit = expected_shares * 0.6

    assert result.total_bets == 1
    assert result.bet_records[0].profit == pytest.approx(expected_profit)
    assert result.final_equity == pytest.approx(10_000.0 + expected_profit)


def test_run_processes_markets_oldest_first() -> None:
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    markets = [
        _market("late", "elections", t0 + timedelta(days=2)),
        _market("early", "elections", t0 + timedelta(days=1)),
    ]
    store = _FakeStore(
        {
            "early": [PricePoint(timestamp=t0, probability=0.45)],
            "late": [PricePoint(timestamp=t0, probability=0.55)],
        }
    )

    seen_order: list[str] = []
    strategy_id = "test_record_order"
    _STRATEGY_REGISTRY[strategy_id] = _RecordingStrategy(seen_order)
    try:
        PolymarketAdapter().run(
            markets=markets,
            store=store,
            strategy_id=strategy_id,
            parameters={},
        )
    finally:
        del _STRATEGY_REGISTRY[strategy_id]

    assert seen_order == ["early", "late"]


def test_category_filter_skips_other_categories() -> None:
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    markets = [
        _market("mkt-election", "elections", t0),
        _market("mkt-sports", "sports", t0 + timedelta(hours=1)),
    ]
    store = _FakeStore(
        {
            "mkt-election": [PricePoint(timestamp=t0 - timedelta(hours=1), probability=0.45)],
            "mkt-sports": [PricePoint(timestamp=t0 - timedelta(hours=1), probability=0.55)],
        }
    )

    seen_order: list[str] = []
    strategy_id = "test_category_filter"
    _STRATEGY_REGISTRY[strategy_id] = _RecordingStrategy(seen_order)
    try:
        PolymarketAdapter(categories=["elections"]).run(
            markets=markets,
            store=store,
            strategy_id=strategy_id,
            parameters={},
        )
    finally:
        del _STRATEGY_REGISTRY[strategy_id]

    assert seen_order == ["mkt-election"]


def test_win_rate_computed_correctly() -> None:
    strategy_id = "test_win_rate"
    _STRATEGY_REGISTRY[strategy_id] = _FixedDecisionStrategy(
        BetDecision(BetAction.BET_YES, estimated_probability=0.7, confidence=1.0)
    )
    try:
        adapter = PolymarketAdapter(initial_capital=10_000.0, max_kelly_fraction=0.1)
        snapshots = [_snapshot(price=0.4, market_id=f"mkt{i}") for i in range(5)]
        outcomes = [1.0, 1.0, 1.0, 0.0, 0.0]
        result = adapter.run_on_snapshots(
            snapshots=snapshots,
            outcomes=outcomes,
            strategy_id=strategy_id,
            parameters={},
        )
    finally:
        del _STRATEGY_REGISTRY[strategy_id]

    assert result.total_bets == 5
    assert result.winning_bets == 3
    assert result.win_rate == pytest.approx(0.6)
