from __future__ import annotations

import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from domains.polymarket.base import BetAction, BetDecision, MarketSnapshot
from domains.polymarket.paper_session import PolymarketPaperConfig, PolymarketPaperSession
from run_polymarket import run_backtest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "run_polymarket.py"


@dataclass
class _AlwaysBetWorker:
    strategy_id: str = "always_bet"

    def evaluate_market(self, snapshot: MarketSnapshot) -> BetDecision:
        del snapshot
        return BetDecision(action=BetAction.BET_YES, estimated_probability=0.8, confidence=1.0)

    def self_tune(self, training_markets, training_outcomes, n_candidates=8) -> None:
        del training_markets, training_outcomes, n_candidates

    def checkpoint(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "current_params": {},
            "cycle_count": 0,
            "optimizer_state": {},
        }

    def restore(self, state: dict) -> None:
        self.strategy_id = str(state.get("strategy_id", self.strategy_id))


def _mock_get_json(path: str, params: dict | None = None):
    del params
    if path == "/markets":
        return [
            {
                "id": "mkt-1",
                "question": "Will event happen?",
                "category": "elections",
            }
        ]
    if path.startswith("/prices-history"):
        return {"history": [{"t": 1, "p": 0.4}, {"t": 2, "p": 0.45}]}
    if path.startswith("/markets/"):
        return {"resolved": False}
    return []


def test_backtest_runs_on_sample_data() -> None:
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--backtest"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    output = completed.stdout
    assert "POLYMARKET BACKTEST" in output

    roi_values = re.findall(r"[+-]\d+\.\d+%", output)
    assert roi_values

    for raw in roi_values:
        value = float(raw.replace("%", "")) / 100.0
        assert math.isfinite(value)


def test_all_strategies_place_at_least_one_bet() -> None:
    summaries = run_backtest(use_llm=False)
    assert len(summaries) == 3
    assert all(summary.run_result.total_bets > 0 for summary in summaries)


def test_determinism() -> None:
    first = run_backtest(use_llm=False)
    second = run_backtest(use_llm=False)

    signature_a = [
        (
            item.strategy_id,
            item.run_result.total_bets,
            round(item.run_result.win_rate, 8),
            round(item.run_result.roi, 8),
            round(item.run_result.total_profit, 8),
        )
        for item in first
    ]
    signature_b = [
        (
            item.strategy_id,
            item.run_result.total_bets,
            round(item.run_result.win_rate, 8),
            round(item.run_result.roi, 8),
            round(item.run_result.total_profit, 8),
        )
        for item in second
    ]

    assert signature_a == signature_b


def test_dry_run_fetches_no_real_bets(monkeypatch) -> None:
    worker = _AlwaysBetWorker()
    session = PolymarketPaperSession(
        PolymarketPaperConfig(initial_capital=1_000.0),
        [worker],  # type: ignore[list-item]
        dry_run=True,
    )
    monkeypatch.setattr(session, "_get_json", _mock_get_json)

    session.run_one_cycle()

    assert session.portfolio.cash == 1_000.0
    assert len(session.portfolio.open_positions) == 0
    assert len(session.portfolio.closed_positions) == 0


def test_checkpoint_resume_continues_from_last_cycle(tmp_path, monkeypatch) -> None:
    checkpoint = tmp_path / "paper_polymarket.json"
    worker = _AlwaysBetWorker(strategy_id="resume_worker")
    config = PolymarketPaperConfig(initial_capital=1_000.0, checkpoint_path=str(checkpoint))
    session = PolymarketPaperSession(config, [worker])  # type: ignore[list-item]
    monkeypatch.setattr(session, "_get_json", _mock_get_json)

    session.run_one_cycle()
    session.run_one_cycle()
    session.save()

    resumed_worker = _AlwaysBetWorker(strategy_id="resume_worker")
    resumed = PolymarketPaperSession.load(str(checkpoint), [resumed_worker])  # type: ignore[list-item]
    monkeypatch.setattr(resumed, "_get_json", _mock_get_json)
    resumed.run_one_cycle()
    resumed.save()

    assert resumed.summary()["cycle_count"] == 3
