from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatchSummary:
    batch_id: str
    iteration: int
    candidate_count: int
    successful_count: int
    best_score: float
