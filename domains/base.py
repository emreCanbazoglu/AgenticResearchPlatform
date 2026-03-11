from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DomainRunResult:
    metrics: dict[str, float]
    score: float
    artifacts: dict[str, str]


class EnvironmentAdapter(Protocol):
    def run(
        self,
        *,
        dataset_id: str,
        strategy_id: str,
        parameters: dict[str, float],
        seed: int,
    ) -> DomainRunResult:
        ...
