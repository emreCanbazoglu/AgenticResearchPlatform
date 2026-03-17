from __future__ import annotations

from core.multi_agent.worker_agent import WorkerAgent
from meta.optimizers.genetic import GeneticOptimizer


def _make_prices(count: int = 100) -> list[float]:
    return [100.0 + ((i % 10) - 5) * 1.5 + (i * 0.1) for i in range(count)]


def _make_agent(seed: int = 42) -> WorkerAgent:
    search_space = {"fast_window": (2, 8), "slow_window": (9, 20)}
    optimizer = GeneticOptimizer(search_space=search_space, seed=seed)
    return WorkerAgent(
        strategy_id="ma_crossover_v1",
        search_space=search_space,
        optimizer=optimizer,
        seed=seed,
    )


def test_self_tune_updates_params(tmp_path) -> None:
    agent = _make_agent()

    agent.self_tune(_make_prices(100), n_candidates=8)

    assert agent._current_params
    assert set(agent._current_params.keys()) == {"fast_window", "slow_window"}


def test_run_eval_uses_current_params() -> None:
    agent = _make_agent()
    prices = _make_prices(100)
    agent.self_tune(prices, n_candidates=8)

    result = agent.run_eval(prices, budget=5_000.0, cycle_idx=0)

    assert result.params_used == agent._current_params
    assert all(value != 0 for value in result.params_used.values())


def test_zero_budget_is_virtual() -> None:
    agent = _make_agent()
    prices = _make_prices(100)

    zero_budget = agent.run_eval(prices, budget=0.0, cycle_idx=0)
    real_budget = agent.run_eval(prices, budget=5_000.0, cycle_idx=0)

    assert zero_budget.is_virtual is True
    assert real_budget.is_virtual is False


def test_virtual_pnl_does_not_affect_real_budget() -> None:
    agent = _make_agent()
    prices = _make_prices(100)

    result = agent.run_eval(prices, budget=0.0, cycle_idx=0)

    assert result.is_virtual is True
    assert result.budget_allocated == 0.0


def test_checkpoint_restore_roundtrip() -> None:
    prices = _make_prices(100)

    original = _make_agent(seed=99)
    for _ in range(3):
        original.self_tune(prices, n_candidates=6)

    state = original.checkpoint()

    restored = _make_agent(seed=99)
    restored.restore(state)

    original_result = original.run_eval(prices, budget=4_000.0, cycle_idx=3)
    restored_result = restored.run_eval(prices, budget=4_000.0, cycle_idx=3)

    assert restored_result == original_result


def test_short_price_list_handled_gracefully() -> None:
    agent = _make_agent()
    short_prices = _make_prices(10)

    agent.self_tune(short_prices, n_candidates=8)
    result = agent.run_eval(short_prices, budget=2_500.0, cycle_idx=0)

    assert agent._cycle_count == 0
    assert result.pnl == 0.0
    assert result.pnl_pct == 0.0
    assert result.score == 0.0
    assert result.trade_count == 0
