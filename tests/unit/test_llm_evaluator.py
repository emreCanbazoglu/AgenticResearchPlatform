from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from domains.polymarket.base import MarketSnapshot
from domains.polymarket.llm_evaluator import LLMEstimate, LLMEvaluator


def _snapshot(*, market_id: str, price: float = 0.5) -> MarketSnapshot:
    return MarketSnapshot(
        market_id=market_id,
        question=f"Question {market_id}?",
        category="politics",
        current_price=price,
        price_history=[max(0.0, price - 0.03), price - 0.01, price],
        days_to_resolution=12.0,
        tags=["tag-a", "tag-b"],
    )


def _mock_anthropic(monkeypatch: pytest.MonkeyPatch, response_text: str) -> None:
    class _FakeMessages:
        def create(self, **kwargs: object) -> object:
            del kwargs
            return SimpleNamespace(content=[SimpleNamespace(text=response_text)])

    class _FakeClient:
        def __init__(self, api_key: str | None = None) -> None:
            del api_key
            self.messages = _FakeMessages()

    monkeypatch.setattr(
        "domains.polymarket.llm_evaluator.anthropic",
        SimpleNamespace(Anthropic=_FakeClient),
    )


def test_estimate_parses_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_anthropic(monkeypatch, '{"probability": 0.64, "confidence": 0.72, "reasoning": "Base rates plus current trend."}')
    evaluator = LLMEvaluator()

    estimate = evaluator.estimate(_snapshot(market_id="m1", price=0.58))

    assert estimate.market_id == "m1"
    assert estimate.market_price == pytest.approx(0.58)
    assert estimate.estimated_probability == pytest.approx(0.64)
    assert estimate.confidence == pytest.approx(0.72)
    assert estimate.model == "claude-3-5-haiku-20241022"
    assert "Base rates" in estimate.reasoning


def test_estimate_handles_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_anthropic(monkeypatch, "this is not json")
    evaluator = LLMEvaluator()

    with pytest.raises(ValueError, match="JSON"):
        evaluator.estimate(_snapshot(market_id="m2"))


def test_estimate_clamps_probability(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_anthropic(monkeypatch, '{"probability": 1.5, "confidence": -0.3, "reasoning": "Extreme estimate."}')
    evaluator = LLMEvaluator()

    estimate = evaluator.estimate(_snapshot(market_id="m3"))

    assert estimate.estimated_probability == pytest.approx(1.0)
    assert estimate.confidence == pytest.approx(0.0)


def test_flag_mispriced_filters_by_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    evaluator = LLMEvaluator(client=object())
    snapshots = [
        _snapshot(market_id="a", price=0.40),
        _snapshot(market_id="b", price=0.40),
        _snapshot(market_id="c", price=0.40),
    ]
    now = datetime.now(UTC)
    estimates = [
        LLMEstimate("a", "qa", 0.40, 0.45, 0.5, "small", evaluator.model, now),
        LLMEstimate("b", "qb", 0.40, 0.52, 0.6, "mid", evaluator.model, now),
        LLMEstimate("c", "qc", 0.40, 0.60, 0.7, "large", evaluator.model, now),
    ]
    monkeypatch.setattr(evaluator, "batch_estimate", lambda snapshots: estimates)

    flagged = evaluator.flag_mispriced(snapshots, threshold=0.10)

    assert len(flagged) == 2
    assert [item.market_id for item in flagged] == ["c", "b"]


def test_cache_hit_skips_api_call(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    evaluator = LLMEvaluator(client=object(), cache_dir=tmp_path)
    snapshot = _snapshot(market_id="cached")
    today_path = tmp_path / f"{datetime.now(UTC).date().isoformat()}.json"
    evaluator.save_estimates(
        today_path,
        [
            LLMEstimate(
                market_id="cached",
                question=snapshot.question,
                market_price=snapshot.current_price,
                estimated_probability=0.63,
                confidence=0.8,
                reasoning="Cached value.",
                model=evaluator.model,
                estimated_at=datetime.now(UTC),
            )
        ],
    )

    monkeypatch.setattr(
        evaluator,
        "estimate",
        lambda market_snapshot: (_ for _ in ()).throw(AssertionError("API should not be called on cache hit")),
    )

    results = evaluator.batch_estimate([snapshot])

    assert len(results) == 1
    assert results[0].market_id == "cached"
    assert results[0].estimated_probability == pytest.approx(0.63)


def test_batch_estimate_returns_all_results(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    evaluator = LLMEvaluator(client=object(), cache_dir=tmp_path)
    snapshots = [_snapshot(market_id=f"m{i}", price=0.4 + i * 0.01) for i in range(5)]

    def _fake_estimate(snapshot: MarketSnapshot) -> LLMEstimate:
        return LLMEstimate(
            market_id=snapshot.market_id,
            question=snapshot.question,
            market_price=snapshot.current_price,
            estimated_probability=min(1.0, snapshot.current_price + 0.1),
            confidence=0.55,
            reasoning="Mocked.",
            model=evaluator.model,
            estimated_at=datetime.now(UTC),
        )

    monkeypatch.setattr(evaluator, "estimate", _fake_estimate)

    results = evaluator.batch_estimate(snapshots)

    assert len(results) == 5
    assert [result.market_id for result in results] == [snapshot.market_id for snapshot in snapshots]
