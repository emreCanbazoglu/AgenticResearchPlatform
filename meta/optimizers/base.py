from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    parameters: dict[str, Any]


class Optimizer(ABC):
    @abstractmethod
    def suggest(self, *, iteration: int, batch_size: int) -> list[Candidate]:
        raise NotImplementedError

    @abstractmethod
    def observe(self, *, scored_candidates: list[tuple[Candidate, float]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def checkpoint(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def restore(self, state: dict[str, Any]) -> None:
        raise NotImplementedError
