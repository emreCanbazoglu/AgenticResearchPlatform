from __future__ import annotations

from core.execution.adapters import get_adapter
from persistence.models import ExperimentJob, ExperimentResult


def execute_job(job: ExperimentJob) -> ExperimentResult:
    try:
        adapter = get_adapter(job.domain)
        run_result = adapter.run(
            dataset_id=job.dataset_id,
            strategy_id=job.strategy_id,
            parameters=job.parameters,
            seed=job.seed,
        )
        return ExperimentResult(
            job_id=job.job_id,
            campaign_id=job.campaign_id,
            batch_id=job.batch_id,
            attempt=job.attempt,
            status="COMPLETED",
            score=run_result.score,
            metrics=run_result.metrics,
            trace_id=job.trace_id,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001
        return ExperimentResult(
            job_id=job.job_id,
            campaign_id=job.campaign_id,
            batch_id=job.batch_id,
            attempt=job.attempt,
            status="FAILED",
            score=-1e9,
            metrics={},
            trace_id=job.trace_id,
            error=str(exc),
        )
