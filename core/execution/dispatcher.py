from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

from core.execution.worker import execute_job
from core.scheduling.priority_queue import JobPriorityQueue
from core.scheduling.quotas import CampaignQuotaTracker
from persistence.models import AuditEvent, DeadLetterRecord, ExperimentJob, ExperimentResult, LineageRecord
from persistence.repositories import SqliteExperimentRepository


def dispatch_jobs(
    *,
    jobs: list[ExperimentJob],
    repository: SqliteExperimentRepository,
    max_workers: int,
    max_concurrent_per_campaign: int,
    max_attempts: int = 2,
    job_timeout_seconds: float = 5.0,
    heartbeat_interval_seconds: float = 0.5,
) -> list[ExperimentResult]:
    queue = JobPriorityQueue()
    for job in jobs:
        repository.insert_job(job)
        repository.insert_lineage(
            LineageRecord(
                job_id=job.job_id,
                campaign_id=job.campaign_id,
                batch_id=job.batch_id,
                candidate_id=job.candidate_id,
                parent_candidate_id=job.parent_candidate_id,
            )
        )
        repository.log_event(
            AuditEvent(
                trace_id=job.trace_id,
                event_type="JOB_QUEUED",
                campaign_id=job.campaign_id,
                batch_id=job.batch_id,
                job_id=job.job_id,
                attempt=job.attempt,
                payload={"priority": job.priority},
            )
        )
        queue.push(job)

    quota_tracker = CampaignQuotaTracker(max_concurrent_per_campaign=max_concurrent_per_campaign)
    scheduled: list[ExperimentJob] = []
    deferred: list[ExperimentJob] = []

    while len(queue) > 0:
        job = queue.pop()
        if quota_tracker.can_schedule(job.campaign_id):
            quota_tracker.mark_started(job.campaign_id)
            scheduled.append(job)
        else:
            deferred.append(job)

    for job in deferred:
        scheduled.append(job)

    final_results: dict[str, ExperimentResult] = {}
    pending = scheduled

    while pending:
        retry_jobs: list[ExperimentJob] = []
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures: dict = {}
            starts: dict = {}
            last_heartbeat: dict = {}
            for job in pending:
                repository.log_event(
                    AuditEvent(
                        trace_id=job.trace_id,
                        event_type="JOB_STARTED",
                        campaign_id=job.campaign_id,
                        batch_id=job.batch_id,
                        job_id=job.job_id,
                        attempt=job.attempt,
                    )
                )
                fut = executor.submit(execute_job, job)
                futures[fut] = job
                starts[fut] = time.monotonic()
                last_heartbeat[fut] = starts[fut]

            while futures:
                done, _ = wait(set(futures.keys()), timeout=0.05, return_when=FIRST_COMPLETED)

                for fut in done:
                    job = futures.pop(fut)
                    starts.pop(fut, None)
                    last_heartbeat.pop(fut, None)
                    result = fut.result()
                    repository.insert_result(result)
                    if result.status == "FAILED" and result.attempt < max_attempts:
                        retry_job = ExperimentJob(
                            job_id=job.job_id,
                            campaign_id=job.campaign_id,
                            batch_id=job.batch_id,
                            candidate_id=job.candidate_id,
                            parent_candidate_id=job.parent_candidate_id,
                            domain=job.domain,
                            dataset_id=job.dataset_id,
                            strategy_id=job.strategy_id,
                            parameters=job.parameters,
                            seed=job.seed,
                            trace_id=job.trace_id,
                            priority=job.priority,
                            attempt=job.attempt + 1,
                        )
                        repository.insert_job(retry_job)
                        repository.log_event(
                            AuditEvent(
                                trace_id=job.trace_id,
                                event_type="JOB_RETRY_SCHEDULED",
                                campaign_id=job.campaign_id,
                                batch_id=job.batch_id,
                                job_id=job.job_id,
                                attempt=retry_job.attempt,
                                payload={"reason": result.error or "failed"},
                            )
                        )
                        retry_jobs.append(retry_job)
                    elif result.status == "FAILED":
                        repository.insert_dead_letter(
                            DeadLetterRecord(
                                job_id=result.job_id,
                                campaign_id=result.campaign_id,
                                batch_id=result.batch_id,
                                attempts=result.attempt,
                                reason=result.error or "unknown_failure",
                            )
                        )
                        repository.log_event(
                            AuditEvent(
                                trace_id=job.trace_id,
                                event_type="JOB_DEAD_LETTERED",
                                campaign_id=job.campaign_id,
                                batch_id=job.batch_id,
                                job_id=job.job_id,
                                attempt=result.attempt,
                                payload={"reason": result.error or "unknown_failure"},
                            )
                        )
                        final_results[result.job_id] = result
                    else:
                        repository.log_event(
                            AuditEvent(
                                trace_id=job.trace_id,
                                event_type="JOB_COMPLETED",
                                campaign_id=job.campaign_id,
                                batch_id=job.batch_id,
                                job_id=job.job_id,
                                attempt=result.attempt,
                                payload={"score": result.score},
                            )
                        )
                        final_results[result.job_id] = result
                    quota_tracker.mark_finished(result.campaign_id)

                now = time.monotonic()
                timed_out = [
                    fut for fut, started in starts.items() if (now - started) > job_timeout_seconds
                ]
                for fut in timed_out:
                    job = futures.pop(fut)
                    starts.pop(fut, None)
                    last_heartbeat.pop(fut, None)
                    fut.cancel()
                    timeout_result = ExperimentResult(
                        job_id=job.job_id,
                        campaign_id=job.campaign_id,
                        batch_id=job.batch_id,
                        attempt=job.attempt,
                        status="FAILED",
                        score=-1e9,
                        metrics={},
                        trace_id=job.trace_id,
                        error=f"lease_timeout_{job_timeout_seconds}s",
                    )
                    repository.insert_result(timeout_result)
                    repository.log_event(
                        AuditEvent(
                            trace_id=job.trace_id,
                            event_type="JOB_TIMEOUT",
                            campaign_id=job.campaign_id,
                            batch_id=job.batch_id,
                            job_id=job.job_id,
                            attempt=job.attempt,
                            payload={"timeout_seconds": job_timeout_seconds},
                        )
                    )
                    if job.attempt < max_attempts:
                        retry_job = ExperimentJob(
                            job_id=job.job_id,
                            campaign_id=job.campaign_id,
                            batch_id=job.batch_id,
                            candidate_id=job.candidate_id,
                            parent_candidate_id=job.parent_candidate_id,
                            domain=job.domain,
                            dataset_id=job.dataset_id,
                            strategy_id=job.strategy_id,
                            parameters=job.parameters,
                            seed=job.seed,
                            trace_id=job.trace_id,
                            priority=job.priority,
                            attempt=job.attempt + 1,
                        )
                        repository.insert_job(retry_job)
                        repository.log_event(
                            AuditEvent(
                                trace_id=job.trace_id,
                                event_type="JOB_RETRY_SCHEDULED",
                                campaign_id=job.campaign_id,
                                batch_id=job.batch_id,
                                job_id=job.job_id,
                                attempt=retry_job.attempt,
                                payload={"reason": timeout_result.error},
                            )
                        )
                        retry_jobs.append(retry_job)
                    else:
                        repository.insert_dead_letter(
                            DeadLetterRecord(
                                job_id=job.job_id,
                                campaign_id=job.campaign_id,
                                batch_id=job.batch_id,
                                attempts=job.attempt,
                                reason=timeout_result.error or "timeout",
                            )
                        )
                        repository.log_event(
                            AuditEvent(
                                trace_id=job.trace_id,
                                event_type="JOB_DEAD_LETTERED",
                                campaign_id=job.campaign_id,
                                batch_id=job.batch_id,
                                job_id=job.job_id,
                                attempt=job.attempt,
                                payload={"reason": timeout_result.error or "timeout"},
                            )
                        )
                        final_results[job.job_id] = timeout_result
                    quota_tracker.mark_finished(job.campaign_id)

                for fut, started in list(last_heartbeat.items()):
                    if fut not in futures:
                        continue
                    if (now - started) >= heartbeat_interval_seconds:
                        job = futures[fut]
                        repository.log_event(
                            AuditEvent(
                                trace_id=job.trace_id,
                                event_type="JOB_HEARTBEAT",
                                campaign_id=job.campaign_id,
                                batch_id=job.batch_id,
                                job_id=job.job_id,
                                attempt=job.attempt,
                            )
                        )
                        last_heartbeat[fut] = now

        pending = sorted(retry_jobs, key=lambda job: (job.priority, job.job_id, job.attempt))

    return [final_results[job_id] for job_id in sorted(final_results)]
