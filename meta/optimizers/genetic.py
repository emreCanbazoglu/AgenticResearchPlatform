from __future__ import annotations

import random
from typing import Any

from meta.optimizers.base import Candidate, Optimizer


class GeneticOptimizer(Optimizer):
    def __init__(self, *, search_space: dict[str, tuple[int, int]], seed: int) -> None:
        self.search_space = search_space
        self._rng = random.Random(seed)
        self._elite: list[Candidate] = []
        self._counter = 0

    # Pairs where the second param must be strictly greater than the first.
    _ORDERED_PAIRS = [("fast_window", "slow_window"), ("fast_period", "slow_period")]

    def _enforce_ordering(self, params: dict[str, Any]) -> None:
        for fast_key, slow_key in self._ORDERED_PAIRS:
            if fast_key in params and slow_key in params:
                if params[slow_key] <= params[fast_key]:
                    params[slow_key] = min(
                        self.search_space[slow_key][1], params[fast_key] + 1
                    )

    def _random_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for key in sorted(self.search_space):
            lo, hi = self.search_space[key]
            params[key] = self._rng.randint(lo, hi)
        self._enforce_ordering(params)
        return params

    def _mutate(self, base: dict[str, Any]) -> dict[str, Any]:
        mutated = dict(base)
        for key in sorted(mutated):
            lo, hi = self.search_space[key]
            step = self._rng.choice([-2, -1, 0, 1, 2])
            mutated[key] = max(lo, min(hi, int(mutated[key]) + step))
        self._enforce_ordering(mutated)
        return mutated

    def suggest(self, *, iteration: int, batch_size: int) -> list[Candidate]:
        candidates: list[Candidate] = []
        elites = self._elite[: max(1, min(2, len(self._elite)))]

        for elite in elites:
            if len(candidates) >= batch_size:
                break
            candidate_id = f"cand-{self._counter:05d}"
            self._counter += 1
            candidates.append(Candidate(candidate_id=candidate_id, parameters=self._mutate(elite.parameters)))

        while len(candidates) < batch_size:
            candidate_id = f"cand-{self._counter:05d}"
            self._counter += 1
            candidates.append(Candidate(candidate_id=candidate_id, parameters=self._random_params()))

        return candidates

    def observe(self, *, scored_candidates: list[tuple[Candidate, float]]) -> None:
        ordered = sorted(scored_candidates, key=lambda item: item[1], reverse=True)
        self._elite = [candidate for candidate, _score in ordered[:3]]

    def checkpoint(self) -> dict[str, Any]:
        return {
            "elite": [candidate.parameters for candidate in self._elite],
            "counter": self._counter,
        }

    def restore(self, state: dict[str, Any]) -> None:
        elite_params = state.get("elite", [])
        self._elite = []
        for params in elite_params:
            candidate_id = f"cand-{self._counter:05d}"
            self._elite.append(Candidate(candidate_id=candidate_id, parameters=dict(params)))
            self._counter += 1
        self._counter = max(self._counter, int(state.get("counter", self._counter)))
