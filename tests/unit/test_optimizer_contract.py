from __future__ import annotations

from meta.optimizers.genetic import GeneticOptimizer


def test_genetic_optimizer_suggest_is_deterministic() -> None:
    a = GeneticOptimizer(search_space={"fast_window": (2, 8), "slow_window": (9, 20)}, seed=123)
    b = GeneticOptimizer(search_space={"fast_window": (2, 8), "slow_window": (9, 20)}, seed=123)

    a_out = a.suggest(iteration=0, batch_size=4)
    b_out = b.suggest(iteration=0, batch_size=4)

    assert [c.parameters for c in a_out] == [c.parameters for c in b_out]
