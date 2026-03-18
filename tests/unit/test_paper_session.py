from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from core.multi_agent import paper_session
from core.multi_agent.paper_session import PaperSession, PaperSessionConfig, fetch_candles
from core.multi_agent.worker_agent import CycleResult


@dataclass
class _StubWorker:
    strategy_id: str
    pnl_pct: float
    _current_params: dict[str, int] = field(default_factory=lambda: {"window": 5})
    _cycle_count: int = 0
    position_size_fraction: float = 1.0
    slippage_rate: float = 0.0

    def self_tune(self, prices: list[float], n_candidates: int = 8) -> None:
        self._cycle_count += 1
        self._current_params = {"window": max(2, len(prices) % 30 + self._cycle_count)}

    def run_eval(self, prices: list[float], budget: float, cycle_idx: int) -> CycleResult:
        is_virtual = budget <= 0
        initial_equity = 10_000.0 if is_virtual else budget
        pnl = initial_equity * self.pnl_pct
        return CycleResult(
            strategy_id=self.strategy_id,
            cycle_idx=cycle_idx,
            budget_allocated=budget,
            is_virtual=is_virtual,
            initial_equity=initial_equity,
            final_equity=initial_equity + pnl,
            pnl=pnl,
            pnl_pct=self.pnl_pct,
            score=self.pnl_pct,
            params_used=dict(self._current_params),
            trade_count=1,
            commission_paid=0.0,
            slippage_paid=0.0,
        )

    def checkpoint(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "current_params": dict(self._current_params),
            "cycle_count": self._cycle_count,
            "optimizer_state": {},
            "position_size_fraction": self.position_size_fraction,
            "slippage_rate": self.slippage_rate,
        }

    def restore(self, state: dict) -> None:
        self.strategy_id = str(state.get("strategy_id", self.strategy_id))
        self._current_params = dict(state.get("current_params", {}))
        self._cycle_count = int(state.get("cycle_count", 0))
        self.position_size_fraction = float(
            state.get("position_size_fraction", self.position_size_fraction)
        )
        self.slippage_rate = float(state.get("slippage_rate", self.slippage_rate))


class _FakeHTTPResponse:
    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _make_prices(count: int) -> list[float]:
    return [100.0 + i * 0.25 for i in range(count)]


def test_run_one_cycle_returns_cycle_summary(monkeypatch) -> None:
    def fake_fetch(symbol: str, interval: str, limit: int) -> list[float]:
        assert symbol == "BTCUSDT"
        assert interval == "30m"
        assert limit == 248
        return _make_prices(248)

    monkeypatch.setattr("core.multi_agent.paper_session.fetch_candles", fake_fetch)
    workers = [_StubWorker("w1", 0.02), _StubWorker("w2", -0.01), _StubWorker("w3", 0.01)]
    session = PaperSession(PaperSessionConfig(), workers)

    summary = session.run_one_cycle()

    assert summary.cycle_idx == 0
    assert len(summary.results) == 3


def test_save_and_load_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "core.multi_agent.paper_session.fetch_candles",
        lambda symbol, interval, limit: _make_prices(limit),
    )
    workers = [_StubWorker("w1", 0.02), _StubWorker("w2", -0.01), _StubWorker("w3", 0.01)]
    session = PaperSession(PaperSessionConfig(), workers)

    session.run_one_cycle()
    session.run_one_cycle()
    checkpoint_path = tmp_path / "session.json"
    session.save(str(checkpoint_path))

    restored_workers = [_StubWorker("w1", 0.02), _StubWorker("w2", -0.01), _StubWorker("w3", 0.01)]
    restored = PaperSession.load(str(checkpoint_path), restored_workers)

    assert restored.summary()["cycle_count"] == 2
    assert restored.director.total_budget == pytest.approx(session.director.total_budget)
    assert restored_workers[0]._current_params == workers[0]._current_params
    assert restored_workers[1]._current_params == workers[1]._current_params
    assert restored_workers[2]._current_params == workers[2]._current_params


def test_load_missing_file_returns_fresh_session(tmp_path) -> None:
    workers = [_StubWorker("w1", 0.01)]

    session = PaperSession.load(str(tmp_path / "nonexistent.json"), workers)

    assert session.summary()["cycle_count"] == 0
    assert session.director.total_budget == pytest.approx(PaperSessionConfig().total_budget)


def test_load_corrupt_file_raises(tmp_path) -> None:
    path = tmp_path / "corrupt.json"
    path.write_text("{ this is not valid json", encoding="utf-8")

    with pytest.raises(ValueError, match="corrupt checkpoint"):
        PaperSession.load(str(path), [_StubWorker("w1", 0.01)])


def test_budget_updates_after_cycle(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.multi_agent.paper_session.fetch_candles",
        lambda symbol, interval, limit: _make_prices(limit),
    )
    workers = [_StubWorker("winner", 0.05), _StubWorker("loser", -0.01)]
    session = PaperSession(PaperSessionConfig(), workers)
    initial_budget = session.director.total_budget

    session.run_one_cycle()

    assert session.director.total_budget != pytest.approx(initial_budget)


def test_fetch_candles_parses_binance_response(monkeypatch) -> None:
    fake_rows = [
        [1, "100", "110", "90", "105.5", "1000"],
        [2, "105", "112", "95", "108.25", "1200"],
    ]
    payload = json.dumps(fake_rows).encode("utf-8")

    captured_url = {"value": ""}

    def fake_urlopen(request, timeout=None):
        captured_url["value"] = getattr(request, "full_url", str(request))
        return _FakeHTTPResponse(payload, status=200)

    monkeypatch.setattr(paper_session.urllib.request, "urlopen", fake_urlopen)

    closes = fetch_candles("BTCUSDT", "30m", 2)

    assert "symbol=BTCUSDT" in captured_url["value"]
    assert "interval=30m" in captured_url["value"]
    assert "limit=2" in captured_url["value"]
    assert closes == [105.5, 108.25]
