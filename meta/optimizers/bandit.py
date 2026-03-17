from __future__ import annotations

import math
import random
from typing import Any

from meta.optimizers.base import Candidate, Optimizer


class BanditOptimizer(Optimizer):
    _ORDERED_PAIRS = [("fast_window", "slow_window"), ("fast_period", "slow_period")]

    def __init__(
        self,
        *,
        search_space: dict[str, tuple[int, int]],
        seed: int,
        pool_size: int = 100,
        exploration_coeff: float = 1.0,
    ) -> None:
        self.search_space = search_space
        self.pool_size = pool_size
        self.exploration_coeff = exploration_coeff
        self._rng = random.Random(seed)

        self._pool: list[Candidate] = []
        self._pool_by_id: dict[str, Candidate] = {}
        self._pulls: dict[str, int] = {}
        self._sum_rewards: dict[str, float] = {}

        self._initialize_pool()

    def _initialize_pool(self) -> None:
        pool: list[Candidate] = []
        for idx in range(self.pool_size):
            candidate_id = f"bandit-{idx:05d}"
            params: dict[str, Any] = {}
            for key in sorted(self.search_space):
                lo, hi = self.search_space[key]
                params[key] = self._rng.randint(lo, hi)
            self._enforce_ordering(params)
            pool.append(Candidate(candidate_id=candidate_id, parameters=params))

        self._set_pool(pool)

    def _set_pool(self, pool: list[Candidate]) -> None:
        self._pool = pool
        self._pool_by_id = {candidate.candidate_id: candidate for candidate in pool}

    def _enforce_ordering(self, params: dict[str, Any]) -> None:
        for fast_key, slow_key in self._ORDERED_PAIRS:
            if fast_key in params and slow_key in params:
                if params[slow_key] <= params[fast_key]:
                    params[slow_key] = min(
                        self.search_space[slow_key][1], params[fast_key] + 1
                    )

    def _ucb1_score(self, *, candidate_id: str, total_pulls: int) -> float:
        pulls = self._pulls.get(candidate_id, 0)
        if pulls == 0:
            return float("inf")
        mean_reward = self._sum_rewards.get(candidate_id, 0.0) / pulls
        exploration = self.exploration_coeff * math.sqrt(
            math.log(total_pulls + 1) / (pulls + 1)
        )
        return mean_reward + exploration

    def suggest(self, *, iteration: int, batch_size: int) -> list[Candidate]:
        total_pulls = sum(self._pulls.values())
        scored = [
            (
                self._ucb1_score(candidate_id=candidate.candidate_id, total_pulls=total_pulls),
                candidate.candidate_id,
                candidate,
            )
            for candidate in self._pool
        ]
        ranked = sorted(scored, key=lambda item: (-item[0], item[1]))

        if not ranked:
            return []

        selected: list[Candidate] = []
        while len(selected) < batch_size:
            selected.extend(candidate for _, _, candidate in ranked)
        return selected[:batch_size]

    def observe(self, *, scored_candidates: list[tuple[Candidate, float]]) -> None:
        for candidate, score in scored_candidates:
            candidate_id = candidate.candidate_id
            if candidate_id not in self._pool_by_id:
                continue
            self._pulls[candidate_id] = self._pulls.get(candidate_id, 0) + 1
            self._sum_rewards[candidate_id] = self._sum_rewards.get(candidate_id, 0.0) + float(score)

    def checkpoint(self) -> dict[str, Any]:
        return {
            "pool": [
                {
                    "candidate_id": candidate.candidate_id,
                    "parameters": dict(candidate.parameters),
                }
                for candidate in self._pool
            ],
            "pulls": dict(self._pulls),
            "sum_rewards": dict(self._sum_rewards),
        }

    def restore(self, state: dict[str, Any]) -> None:
        pool_state = state.get("pool", [])
        pool = [
            Candidate(
                candidate_id=str(item["candidate_id"]),
                parameters=dict(item["parameters"]),
            )
            for item in pool_state
        ]
        self._set_pool(pool)
        self._pulls = {str(key): int(value) for key, value in dict(state.get("pulls", {})).items()}
        self._sum_rewards = {
            str(key): float(value) for key, value in dict(state.get("sum_rewards", {})).items()
        }
