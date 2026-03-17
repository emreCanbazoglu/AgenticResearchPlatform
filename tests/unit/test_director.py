from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.multi_agent.director import Director
from core.multi_agent.worker_agent import CycleResult


@dataclass
class _StubWorker:
    strategy_id: str
    pnl_pct: float
    _tuned: int = 0

    def self_tune(self, prices: list[float], n_candidates: int = 8) -> None:
        self._tuned += 1

    def run_eval(self, prices: list[float], budget: float, cycle_idx: int) -> CycleResult:
        is_virtual = budget <= 0
        initial_equity = 10_000.0 if is_virtual else budget
        pnl = initial_equity * self.pnl_pct
        final_equity = initial_equity + pnl
        return CycleResult(
            strategy_id=self.strategy_id,
            cycle_idx=cycle_idx,
            budget_allocated=budget,
            is_virtual=is_virtual,
            initial_equity=initial_equity,
            final_equity=final_equity,
            pnl=pnl,
            pnl_pct=self.pnl_pct,
            score=0.0,
            params_used={},
            trade_count=0,
        )


def _make_prices(count: int = 200) -> list[float]:
    return [100.0 + (i * 0.25) for i in range(count)]


def test_equal_allocation_on_first_cycle() -> None:
    workers = [
        _StubWorker("w1", 0.0),
        _StubWorker("w2", 0.0),
        _StubWorker("w3", 0.0),
    ]
    director = Director(total_budget=30_000.0, workers=workers)

    allocations = director._allocate()

    assert allocations == {
        "w1": pytest.approx(10_000.0),
        "w2": pytest.approx(10_000.0),
        "w3": pytest.approx(10_000.0),
    }


def test_virtual_workers_excluded_from_pool_pnl() -> None:
    workers = [
        _StubWorker("real", 0.10),
        _StubWorker("virtual", 1.00),
    ]
    director = Director(total_budget=10_000.0, workers=workers, min_budget_fraction=0.2)
    director._observe("real", 0.10)
    for _ in range(30):
        director._observe("virtual", -0.90)
    director._completed_cycles = 30

    session = director.run_session(_make_prices(200), cycle_size=48, lookback_size=100)

    first_cycle = session.cycle_summaries[0]
    virtual_result = next(result for result in first_cycle.results if result.strategy_id == "virtual")
    assert virtual_result.is_virtual is True
    assert first_cycle.total_budget_after == pytest.approx(
        first_cycle.total_budget_before + 1_000.0
    )


def test_real_pnl_updates_total_budget() -> None:
    workers = [_StubWorker("only", 0.10)]
    director = Director(total_budget=10_000.0, workers=workers)

    session = director.run_session(_make_prices(200), cycle_size=48, lookback_size=100)

    assert session.cycle_summaries[0].total_budget_after == pytest.approx(11_000.0)


def test_poor_performer_gets_virtual_after_many_cycles() -> None:
    workers = [_StubWorker("good", 0.05), _StubWorker("poor", -0.5)]
    director = Director(total_budget=10_000.0, workers=workers, min_budget_fraction=0.1)

    for _ in range(40):
        director._observe("good", 0.05)
        director._observe("poor", -0.5)
    director._completed_cycles = 40

    allocations = director._allocate()

    assert allocations["poor"] == 0.0
    assert allocations["good"] == pytest.approx(10_000.0)


def test_session_runs_correct_number_of_cycles() -> None:
    workers = [_StubWorker("w1", 0.0)]
    director = Director(total_budget=10_000.0, workers=workers)

    session = director.run_session(_make_prices(200), cycle_size=48, lookback_size=100)

    assert session.n_cycles == 2
    assert len(session.cycle_summaries) == 2


def test_session_result_final_budget_consistent() -> None:
    workers = [_StubWorker("w1", 0.10), _StubWorker("w2", -0.05)]
    director = Director(total_budget=20_000.0, workers=workers)

    session = director.run_session(_make_prices(300), cycle_size=48, lookback_size=100)

    real_pnl = 0.0
    for cycle in session.cycle_summaries:
        for result in cycle.results:
            if not result.is_virtual:
                real_pnl += result.pnl

    assert session.final_budget == pytest.approx(session.initial_budget + real_pnl)
