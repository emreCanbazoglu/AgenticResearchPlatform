from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from domains.polymarket.base import BetAction, BetDecision, MarketSnapshot
from domains.polymarket.paper_session import (
    PolymarketPaperConfig,
    PolymarketPaperSession,
    VirtualPosition,
)


@dataclass
class _StubWorker:
    strategy_id: str
    decision: BetDecision

    def evaluate_market(self, snapshot: MarketSnapshot) -> BetDecision:
        del snapshot
        return self.decision

    def self_tune(self, training_markets, training_outcomes, n_candidates=8) -> None:
        del training_markets, training_outcomes, n_candidates

    def checkpoint(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "current_params": {},
            "cycle_count": 0,
            "optimizer_state": {},
            "position_size_fraction": 1.0,
            "slippage_rate": 0.0,
        }

    def restore(self, state: dict) -> None:
        self.strategy_id = str(state.get("strategy_id", self.strategy_id))


class _FakeHTTPResponse:
    def __init__(self, payload: object, status: int = 200):
        self._payload = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _mock_urlopen(monkeypatch, responses: dict[str, object]) -> None:
    def fake_urlopen(url: str):
        for path, payload in responses.items():
            if path in url:
                return _FakeHTTPResponse(payload, status=200)
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr("domains.polymarket.paper_session.urllib.request.urlopen", fake_urlopen)


def test_resolution_check_closes_position(tmp_path, monkeypatch) -> None:
    workers = [
        _StubWorker(
            "w1",
            BetDecision(
                action=BetAction.PASS,
                estimated_probability=0.5,
                confidence=0.0,
            ),
        )
    ]
    session = PolymarketPaperSession(
        PolymarketPaperConfig(initial_capital=10_000.0, checkpoint_path=str(tmp_path / "ckpt.json")),
        workers,
    )
    session.portfolio.cash = 9_900.0
    session.portfolio.open_positions = [
        VirtualPosition(
            market_id="mkt-1",
            question="Will it happen?",
            action=BetAction.BET_YES,
            entry_price=0.4,
            bet_amount=100.0,
            shares=250.0,
            opened_at=datetime.now(tz=timezone.utc),
            estimated_prob=0.7,
            strategy_id="w1",
        )
    ]

    _mock_urlopen(
        monkeypatch,
        {
            "/markets?active=true": [],
            "/markets/mkt-1": {"resolved": True, "outcome": "yes", "category": "elections"},
        },
    )

    session.run_one_cycle()

    assert len(session.portfolio.open_positions) == 0
    assert len(session.portfolio.closed_positions) == 1
    assert session.portfolio.closed_positions[0].profit == 150.0
    assert session.portfolio.cash == 10_150.0


def test_new_bets_deduct_from_cash(tmp_path, monkeypatch) -> None:
    workers = [
        _StubWorker(
            "w1",
            BetDecision(
                action=BetAction.BET_YES,
                estimated_probability=0.8,
                confidence=1.0,
            ),
        )
    ]
    session = PolymarketPaperSession(
        PolymarketPaperConfig(initial_capital=1_000.0, checkpoint_path=str(tmp_path / "ckpt.json")),
        workers,
    )

    _mock_urlopen(
        monkeypatch,
        {
            "/markets?active=true": [
                {
                    "id": "mkt-1",
                    "question": "Will event happen?",
                    "category": "elections",
                }
            ],
            "/prices-history?market=mkt-1": {"history": [{"t": 1, "p": 0.5}, {"t": 2, "p": 0.5}]},
        },
    )

    session.run_one_cycle()

    assert session.portfolio.cash < 1_000.0
    assert len(session.portfolio.open_positions) == 1


def test_pass_decisions_create_no_positions(tmp_path, monkeypatch) -> None:
    workers = [
        _StubWorker(
            "w1",
            BetDecision(
                action=BetAction.PASS,
                estimated_probability=0.5,
                confidence=0.0,
            ),
        )
    ]
    session = PolymarketPaperSession(
        PolymarketPaperConfig(initial_capital=1_000.0, checkpoint_path=str(tmp_path / "ckpt.json")),
        workers,
    )

    _mock_urlopen(
        monkeypatch,
        {
            "/markets?active=true": [
                {
                    "id": "mkt-1",
                    "question": "Will event happen?",
                    "category": "elections",
                }
            ],
            "/prices-history?market=mkt-1": {"history": [{"t": 1, "p": 0.5}, {"t": 2, "p": 0.5}]},
        },
    )

    session.run_one_cycle()

    assert session.portfolio.cash == 1_000.0
    assert len(session.portfolio.open_positions) == 0


def test_checkpoint_roundtrip(tmp_path, monkeypatch) -> None:
    workers = [
        _StubWorker(
            "w1",
            BetDecision(
                action=BetAction.BET_NO,
                estimated_probability=0.2,
                confidence=1.0,
            ),
        )
    ]
    session = PolymarketPaperSession(
        PolymarketPaperConfig(initial_capital=1_000.0, checkpoint_path=str(tmp_path / "ckpt.json")),
        workers,
    )

    _mock_urlopen(
        monkeypatch,
        {
            "/markets?active=true": [
                {
                    "id": "mkt-1",
                    "question": "Will event happen?",
                    "category": "elections",
                }
            ],
            "/prices-history?market=mkt-1": {"history": [{"t": 1, "p": 0.7}, {"t": 2, "p": 0.7}]},
        },
    )

    session.run_one_cycle()
    checkpoint = tmp_path / "paper_polymarket.json"
    session.save(str(checkpoint))

    restored_workers = [
        _StubWorker(
            "w1",
            BetDecision(
                action=BetAction.PASS,
                estimated_probability=0.5,
                confidence=0.0,
            ),
        )
    ]
    restored = PolymarketPaperSession.load(str(checkpoint), restored_workers)

    assert restored.summary() == session.summary()
    assert len(restored.portfolio.open_positions) == len(session.portfolio.open_positions)


def test_load_from_missing_file_creates_fresh_session(tmp_path) -> None:
    workers = [
        _StubWorker(
            "w1",
            BetDecision(
                action=BetAction.PASS,
                estimated_probability=0.5,
                confidence=0.0,
            ),
        )
    ]

    session = PolymarketPaperSession.load(str(tmp_path / "missing.json"), workers)

    summary = session.summary()
    assert summary["cycle_count"] == 0
    assert summary["cash"] == 10_000.0
    assert summary["open_positions"] == 0
