from __future__ import annotations

from meta.optimizers.base import Candidate, Optimizer


class BayesianOptimizer(Optimizer):
    """Deterministic placeholder for MVP.

    This keeps the interface stable while we iterate on a full TPE/GP engine.
    """

    def __init__(self, *, defaults: dict[str, int]) -> None:
        self.defaults = defaults
        self._counter = 0

    def suggest(self, *, iteration: int, batch_size: int) -> list[Candidate]:
        out: list[Candidate] = []
        for _ in range(batch_size):
            cid = f"bo-{self._counter:05d}"
            self._counter += 1
            out.append(Candidate(candidate_id=cid, parameters=dict(self.defaults)))
        return out

    def observe(self, *, scored_candidates: list[tuple[Candidate, float]]) -> None:
        return

    def checkpoint(self) -> dict[str, int]:
        return {"counter": self._counter}

    def restore(self, state: dict[str, int]) -> None:
        self._counter = int(state.get("counter", self._counter))
