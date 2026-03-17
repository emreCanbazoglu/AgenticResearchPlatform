from __future__ import annotations

import pytest

from core.multi_agent.worker_agent import WorkerAgent
from meta.optimizers.genetic import GeneticOptimizer


PRICES_WITH_TRADES = [10.0, 10.0, 10.0, 12.0, 8.0] + [8.0] * 15


def _make_worker(
    *,
    position_size_fraction: float = 1.0,
    slippage_rate: float = 0.0,
    commission_rate: float = 0.001,
) -> WorkerAgent:
    search_space = {"fast_window": (2, 2), "slow_window": (3, 3)}
    return WorkerAgent(
        strategy_id="ma_crossover_v1",
        search_space=search_space,
        optimizer=GeneticOptimizer(search_space=search_space, seed=123),
        seed=123,
        position_size_fraction=position_size_fraction,
        slippage_rate=slippage_rate,
        commission_rate=commission_rate,
    )


def test_worker_passes_slippage_to_adapter() -> None:
    worker = _make_worker(slippage_rate=0.01, commission_rate=0.0)

    result = worker.run_eval(PRICES_WITH_TRADES, budget=10_000.0, cycle_idx=0)

    assert result.trade_count > 0
    assert result.slippage_paid > 0.0


def test_worker_passes_position_fraction_to_adapter() -> None:
    full_size_worker = _make_worker(position_size_fraction=1.0, commission_rate=0.0)
    half_size_worker = _make_worker(position_size_fraction=0.5, commission_rate=0.0)

    full_size_result = full_size_worker.run_eval(PRICES_WITH_TRADES, budget=10_000.0, cycle_idx=0)
    half_size_result = half_size_worker.run_eval(PRICES_WITH_TRADES, budget=10_000.0, cycle_idx=0)

    assert full_size_result.trade_count > 0
    assert half_size_result.trade_count == full_size_result.trade_count
    assert half_size_result.final_equity > 0.0
    assert half_size_result.final_equity > full_size_result.final_equity


def test_default_worker_has_zero_slippage() -> None:
    worker = _make_worker(commission_rate=0.0)

    result = worker.run_eval(PRICES_WITH_TRADES, budget=10_000.0, cycle_idx=0)

    assert result.slippage_paid == pytest.approx(0.0)


def test_checkpoint_includes_realism_params() -> None:
    worker = _make_worker(position_size_fraction=0.75, slippage_rate=0.0025)

    checkpoint = worker.checkpoint()

    assert checkpoint["position_size_fraction"] == worker.position_size_fraction
    assert checkpoint["slippage_rate"] == worker.slippage_rate


def test_restore_preserves_realism_params() -> None:
    original = _make_worker(position_size_fraction=0.65, slippage_rate=0.004)
    checkpoint = original.checkpoint()

    restored = _make_worker(position_size_fraction=1.0, slippage_rate=0.0)
    restored.restore(checkpoint)

    assert restored.position_size_fraction == pytest.approx(original.position_size_fraction)
    assert restored.slippage_rate == pytest.approx(original.slippage_rate)
