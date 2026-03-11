from __future__ import annotations

from dataclasses import dataclass

from meta.optimizers.base import Candidate
from persistence.models import ExperimentJob


@dataclass(frozen=True)
class BatchContext:
    campaign_id: str
    batch_id: str
    domain: str
    dataset_id: str
    strategy_id: str
    base_seed: int
    trace_id: str
    priority: str = "standard"


def build_jobs(context: BatchContext, candidates: list[Candidate]) -> list[ExperimentJob]:
    jobs: list[ExperimentJob] = []
    for idx, candidate in enumerate(candidates):
        jobs.append(
            ExperimentJob(
                job_id=f"{context.batch_id}-job-{idx:04d}",
                campaign_id=context.campaign_id,
                batch_id=context.batch_id,
                candidate_id=candidate.candidate_id,
                parent_candidate_id=None,
                domain=context.domain,
                dataset_id=context.dataset_id,
                strategy_id=context.strategy_id,
                parameters=candidate.parameters,
                seed=context.base_seed + idx,
                trace_id=context.trace_id,
                priority=context.priority,
                attempt=1,
            )
        )
    return jobs
