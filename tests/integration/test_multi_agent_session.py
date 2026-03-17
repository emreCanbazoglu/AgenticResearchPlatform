from __future__ import annotations

import csv
from pathlib import Path

import pytest

from core.multi_agent.director import Director
from core.multi_agent.worker_agent import WorkerAgent
from meta.optimizers.genetic import GeneticOptimizer


def _load_prices() -> list[float]:
    primary = Path("data/trading/btc_usdt_30m.csv")
    fallback = Path("data/trading/btc_usdt_1d.csv")
    dataset = primary if primary.exists() else fallback

    with dataset.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return [float(row["close"]) for row in reader]


def _make_workers(seed: int) -> list[WorkerAgent]:
    ma_space = {"fast_window": (2, 20), "slow_window": (5, 60)}
    rsi_space = {"period": (5, 30), "overbought": (60, 80), "oversold": (20, 40)}
    macd_space = {"fast_period": (5, 15), "slow_period": (20, 40), "signal_period": (5, 15)}
    return [
        WorkerAgent(
            strategy_id="ma_crossover_v1",
            search_space=ma_space,
            optimizer=GeneticOptimizer(search_space=ma_space, seed=seed),
            seed=seed,
            virtual_budget=10_000.0,
        ),
        WorkerAgent(
            strategy_id="rsi_v1",
            search_space=rsi_space,
            optimizer=GeneticOptimizer(search_space=rsi_space, seed=seed + 1),
            seed=seed + 1,
            virtual_budget=10_000.0,
        ),
        WorkerAgent(
            strategy_id="macd_v1",
            search_space=macd_space,
            optimizer=GeneticOptimizer(search_space=macd_space, seed=seed + 2),
            seed=seed + 2,
            virtual_budget=10_000.0,
        ),
    ]


def _run_session(seed: int):
    director = Director(total_budget=30_000.0, workers=_make_workers(seed))
    return director.run_session(
        all_prices=_load_prices(),
        cycle_size=48,
        lookback_size=200,
        n_tune_candidates=8,
    )


def _snapshot(session) -> list[tuple]:
    rows: list[tuple] = []
    for cycle in session.cycle_summaries:
        allocations = tuple(
            (sid, round(amount, 8)) for sid, amount in sorted(cycle.allocations.items())
        )
        results = tuple(
            (
                result.strategy_id,
                result.is_virtual,
                round(result.budget_allocated, 8),
                round(result.pnl, 8),
                round(result.pnl_pct, 8),
                round(result.score, 8),
            )
            for result in cycle.results
        )
        rows.append(
            (
                cycle.cycle_idx,
                round(cycle.total_budget_before, 8),
                round(cycle.total_budget_after, 8),
                allocations,
                results,
            )
        )
    return rows


def test_three_worker_session_runs_end_to_end(tmp_path) -> None:
    session = _run_session(seed=42)

    assert session.n_cycles >= 1
    assert session.final_budget > 0
    assert any(
        (not result.is_virtual) and (result.pnl != 0.0)
        for cycle in session.cycle_summaries
        for result in cycle.results
    )
    first_alloc_sum = sum(session.cycle_summaries[0].allocations.values())
    assert first_alloc_sum == pytest.approx(session.initial_budget)


def test_session_is_deterministic() -> None:
    left = _run_session(seed=99)
    right = _run_session(seed=99)

    assert left.n_cycles == right.n_cycles
    assert left.final_budget == pytest.approx(right.final_budget)
    assert _snapshot(left) == _snapshot(right)
