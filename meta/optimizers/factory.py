from __future__ import annotations

from meta.optimizers.bayesian import BayesianOptimizer
from meta.optimizers.base import Optimizer
from meta.optimizers.genetic import GeneticOptimizer


def make_optimizer(name: str, *, search_space: dict[str, tuple[int, int]], seed: int) -> Optimizer:
    if name == "genetic":
        return GeneticOptimizer(search_space=search_space, seed=seed)
    if name == "bayesian":
        defaults = {key: (bounds[0] + bounds[1]) // 2 for key, bounds in search_space.items()}
        if "fast_window" in defaults and "slow_window" in defaults and defaults["slow_window"] <= defaults["fast_window"]:
            defaults["slow_window"] = defaults["fast_window"] + 1
        return BayesianOptimizer(defaults=defaults)
    raise ValueError(f"unsupported optimizer: {name}")
