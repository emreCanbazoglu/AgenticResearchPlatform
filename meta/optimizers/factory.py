from __future__ import annotations

from meta.optimizers.bayesian import BayesianOptimizer
from meta.optimizers.bandit import BanditOptimizer
from meta.optimizers.base import Optimizer
from meta.optimizers.genetic import GeneticOptimizer


def make_optimizer(name: str, *, search_space: dict[str, tuple[int, int]], seed: int) -> Optimizer:
    if name == "genetic":
        return GeneticOptimizer(search_space=search_space, seed=seed)
    if name == "bandit":
        return BanditOptimizer(search_space=search_space, seed=seed)
    if name == "bayesian":
        return BayesianOptimizer(search_space=search_space, seed=seed)
    raise ValueError(f"unsupported optimizer: {name}")
