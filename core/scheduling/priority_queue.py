from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from core.scheduling.policy import priority_rank
from persistence.models import ExperimentJob


@dataclass(order=True)
class _PrioritizedItem:
    rank: int
    sequence: int
    job: ExperimentJob = field(compare=False)


class JobPriorityQueue:
    def __init__(self) -> None:
        self._heap: list[_PrioritizedItem] = []
        self._seq = 0

    def push(self, job: ExperimentJob) -> None:
        heapq.heappush(self._heap, _PrioritizedItem(rank=priority_rank(job.priority), sequence=self._seq, job=job))
        self._seq += 1

    def pop(self) -> ExperimentJob:
        return heapq.heappop(self._heap).job

    def __len__(self) -> int:
        return len(self._heap)
