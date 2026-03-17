from __future__ import annotations

import math
import random
from typing import Any

from meta.optimizers.base import Candidate, Optimizer


class BayesianOptimizer(Optimizer):
    # Pairs where the second param must be strictly greater than the first.
    _ORDERED_PAIRS = [("fast_window", "slow_window"), ("fast_period", "slow_period")]

    def __init__(
        self,
        *,
        search_space: dict[str, tuple[int, int]],
        seed: int,
        n_startup_trials: int = 10,
        gamma: float = 0.25,
    ) -> None:
        self.search_space = search_space
        self._rng = random.Random(seed)
        self._n_startup_trials = n_startup_trials
        self._gamma = gamma
        self._counter = 0
        self._history: list[tuple[dict[str, Any], float]] = []

    def _enforce_ordering(self, params: dict[str, Any]) -> None:
        for fast_key, slow_key in self._ORDERED_PAIRS:
            if fast_key in params and slow_key in params:
                if params[slow_key] <= params[fast_key]:
                    params[slow_key] = min(self.search_space[slow_key][1], params[fast_key] + 1)

    def _random_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for key in sorted(self.search_space):
            lo, hi = self.search_space[key]
            params[key] = self._rng.randint(lo, hi)
        self._enforce_ordering(params)
        return params

    def _discrete_kde(self, values: list[int], *, lo: int, hi: int) -> dict[int, float]:
        support = list(range(lo, hi + 1))
        if not support:
            return {}

        counts: dict[int, float] = {x: 1e-12 for x in support}
        if not values:
            uniform = 1.0 / float(len(support))
            return {x: uniform for x in support}

        for value in values:
            center = int(value)
            for neighbor in (center - 1, center, center + 1):
                clipped = max(lo, min(hi, neighbor))
                counts[clipped] += 1.0

        total = sum(counts.values())
        if total <= 0:
            uniform = 1.0 / float(len(support))
            return {x: uniform for x in support}
        return {x: (counts[x] / total) for x in support}

    def _sample_from_pmf(self, pmf: dict[int, float]) -> int:
        r = self._rng.random()
        cumulative = 0.0
        last = 0
        for value in sorted(pmf):
            last = value
            cumulative += pmf[value]
            if r <= cumulative:
                return value
        return last

    def _tpe_params(self) -> dict[str, Any]:
        ranked = sorted(self._history, key=lambda item: item[1], reverse=True)
        good_size = max(1, int(math.ceil(len(ranked) * self._gamma)))
        good = ranked[:good_size]
        bad = ranked[good_size:] or ranked[good_size - 1 : good_size]

        good_pmfs: dict[str, dict[int, float]] = {}
        bad_pmfs: dict[str, dict[int, float]] = {}

        for key in sorted(self.search_space):
            lo, hi = self.search_space[key]
            good_values = [int(params[key]) for params, _ in good]
            bad_values = [int(params[key]) for params, _ in bad]
            good_pmfs[key] = self._discrete_kde(good_values, lo=lo, hi=hi)
            bad_pmfs[key] = self._discrete_kde(bad_values, lo=lo, hi=hi)

        draw_count = max(24, len(self.search_space) * 8)
        best_params: dict[str, Any] | None = None
        best_score = float("-inf")

        for _ in range(draw_count):
            sampled: dict[str, Any] = {}
            score = 0.0
            for key in sorted(self.search_space):
                x = self._sample_from_pmf(good_pmfs[key])
                sampled[key] = x
                l_prob = good_pmfs[key].get(x, 1e-12)
                g_prob = bad_pmfs[key].get(x, 1e-12)
                score += math.log(max(l_prob, 1e-12)) - math.log(max(g_prob, 1e-12))

            self._enforce_ordering(sampled)
            if score > best_score:
                best_params = sampled
                best_score = score

        return best_params if best_params is not None else self._random_params()

    def suggest(self, *, iteration: int, batch_size: int) -> list[Candidate]:
        out: list[Candidate] = []
        for _ in range(batch_size):
            if self._counter < self._n_startup_trials or not self._history:
                params = self._random_params()
            else:
                params = self._tpe_params()

            cid = f"bo-{self._counter:05d}"
            self._counter += 1
            out.append(Candidate(candidate_id=cid, parameters=params))
        return out

    def observe(self, *, scored_candidates: list[tuple[Candidate, float]]) -> None:
        for candidate, score in scored_candidates:
            self._history.append((dict(candidate.parameters), float(score)))

    def checkpoint(self) -> dict[str, Any]:
        return {
            "history": [
                {"params": dict(params), "score": float(score)} for params, score in self._history
            ],
            "counter": self._counter,
            "rng_state": self._rng.getstate(),
        }

    def restore(self, state: dict[str, Any]) -> None:
        history = state.get("history", [])
        self._history = []
        for item in history:
            params = dict(item.get("params", {}))
            score = float(item.get("score", 0.0))
            self._history.append((params, score))

        self._counter = int(state.get("counter", self._counter))

        rng_state = state.get("rng_state")
        if rng_state is not None:
            self._rng.setstate(self._to_tuple(rng_state))

    def _to_tuple(self, value: Any) -> Any:
        if isinstance(value, list):
            return tuple(self._to_tuple(item) for item in value)
        if isinstance(value, dict):
            return {key: self._to_tuple(item) for key, item in value.items()}
        return value
