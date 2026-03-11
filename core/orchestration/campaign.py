from __future__ import annotations

from dataclasses import dataclass

from core.execution.dispatcher import dispatch_jobs
from core.execution.planner import BatchContext, build_jobs
from core.orchestration.batch import BatchSummary
from core.orchestration.state_machine import CampaignStatus
from core.reproducibility.snapshot import CampaignSnapshot
from observability.tracing import new_trace_id
from meta.optimizers.base import Candidate
from meta.optimizers.factory import make_optimizer
from persistence.models import AuditEvent, BatchRecord, CampaignRecord
from persistence.repositories import SqliteExperimentRepository


@dataclass(frozen=True)
class CampaignConfig:
    campaign_id: str
    domain: str
    dataset_id: str
    strategy_id: str
    iterations: int
    batch_size: int
    seed: int
    db_path: str
    priority: str = "standard"
    max_workers: int = 4
    max_concurrent_per_campaign: int = 8
    search_space: dict[str, tuple[int, int]] = None
    optimizer: str = "genetic"
    resume_from_latest: bool = False
    stop_after_iteration: int | None = None


@dataclass(frozen=True)
class CampaignRunOutput:
    snapshot_fingerprint: str
    batch_summaries: list[BatchSummary]
    best_score: float
    best_parameters: dict[str, float]


def run_campaign(config: CampaignConfig) -> CampaignRunOutput:
    default_spaces: dict[str, dict[str, tuple[int, int]]] = {
        "trading": {"fast_window": (2, 20), "slow_window": (5, 60)},
        "game_economy": {"reward_multiplier": (1, 3), "sink_multiplier": (1, 3)},
    }
    search_space = config.search_space or default_spaces.get(config.domain, {})
    if not search_space:
        raise ValueError(f"no search space configured for domain={config.domain}")
    snapshot = CampaignSnapshot(
        campaign_id=config.campaign_id,
        domain=config.domain,
        optimizer=config.optimizer,
        dataset_id=config.dataset_id,
        strategy_id=config.strategy_id,
        iterations=config.iterations,
        batch_size=config.batch_size,
        seed=config.seed,
        parameters_space={k: list(v) for k, v in search_space.items()},
    )
    fingerprint = snapshot.fingerprint()

    repository = SqliteExperimentRepository(config.db_path)
    optimizer = make_optimizer(config.optimizer, search_space=search_space, seed=config.seed)
    trace_id = new_trace_id()
    start_iteration = 0
    repository.upsert_campaign(
        CampaignRecord(
            campaign_id=config.campaign_id,
            status=CampaignStatus.RUNNING.value,
            snapshot_fingerprint=fingerprint,
        )
    )
    repository.log_event(
        AuditEvent(
            trace_id=trace_id,
            event_type="CAMPAIGN_STARTED",
            campaign_id=config.campaign_id,
            payload={"optimizer": config.optimizer, "domain": config.domain},
        )
    )

    best_score = float("-inf")
    best_parameters: dict[str, float] = {}
    if config.resume_from_latest:
        checkpoint = repository.get_latest_checkpoint(config.campaign_id)
        if checkpoint is not None:
            optimizer.restore(checkpoint["optimizer_state"])
            best_score = float(checkpoint["best_score"])
            best_parameters = {
                key: float(value) for key, value in checkpoint["best_parameters"].items()
            }
            start_iteration = int(checkpoint["iteration"]) + 1
            trace_id = str(checkpoint["trace_id"])
            repository.log_event(
                AuditEvent(
                    trace_id=trace_id,
                    event_type="CAMPAIGN_RESUMED",
                    campaign_id=config.campaign_id,
                    payload={"start_iteration": start_iteration},
                )
            )
    summaries: list[BatchSummary] = []

    for iteration in range(start_iteration, config.iterations):
        batch_id = f"{config.campaign_id}-batch-{iteration:03d}"
        repository.upsert_batch(
            BatchRecord(
                batch_id=batch_id,
                campaign_id=config.campaign_id,
                iteration=iteration,
                status=CampaignStatus.RUNNING.value,
            )
        )
        repository.log_event(
            AuditEvent(
                trace_id=trace_id,
                event_type="BATCH_STARTED",
                campaign_id=config.campaign_id,
                batch_id=batch_id,
                payload={"iteration": iteration},
            )
        )
        candidates: list[Candidate] = optimizer.suggest(iteration=iteration, batch_size=config.batch_size)
        context = BatchContext(
            campaign_id=config.campaign_id,
            batch_id=batch_id,
            domain=config.domain,
            dataset_id=config.dataset_id,
            strategy_id=config.strategy_id,
            base_seed=config.seed * 1000 + iteration * 100,
            trace_id=trace_id,
            priority=config.priority,
        )
        jobs = build_jobs(context, candidates)
        results = dispatch_jobs(
            jobs=jobs,
            repository=repository,
            max_workers=config.max_workers,
            max_concurrent_per_campaign=config.max_concurrent_per_campaign,
            max_attempts=2,
        )

        score_by_job = {result.job_id: result.score for result in results if result.status == "COMPLETED"}
        scored_candidates: list[tuple[Candidate, float]] = []

        successful = 0
        for idx, candidate in enumerate(candidates):
            job_id = f"{batch_id}-job-{idx:04d}"
            score = score_by_job.get(job_id, -1e9)
            if score > -1e8:
                successful += 1
            scored_candidates.append((candidate, score))
            if score > best_score:
                best_score = score
                best_parameters = {k: float(v) for k, v in candidate.parameters.items()}

        optimizer.observe(scored_candidates=scored_candidates)
        batch_status = CampaignStatus.COMPLETED.value if successful == len(candidates) else CampaignStatus.PARTIAL.value
        repository.upsert_batch(
            BatchRecord(
                batch_id=batch_id,
                campaign_id=config.campaign_id,
                iteration=iteration,
                status=batch_status,
            )
        )
        repository.log_event(
            AuditEvent(
                trace_id=trace_id,
                event_type="BATCH_FINISHED",
                campaign_id=config.campaign_id,
                batch_id=batch_id,
                payload={"status": batch_status, "successful": successful, "total": len(candidates)},
            )
        )
        summaries.append(
            BatchSummary(
                batch_id=batch_id,
                iteration=iteration,
                candidate_count=len(candidates),
                successful_count=successful,
                best_score=max((score for _, score in scored_candidates), default=-1e9),
            )
        )
        repository.save_checkpoint(
            campaign_id=config.campaign_id,
            iteration=iteration,
            optimizer_state=optimizer.checkpoint(),
            best_score=best_score,
            best_parameters=best_parameters,
            trace_id=trace_id,
        )
        if config.stop_after_iteration is not None and iteration >= config.stop_after_iteration:
            repository.upsert_campaign(
                CampaignRecord(
                    campaign_id=config.campaign_id,
                    status=CampaignStatus.PARTIAL.value,
                    snapshot_fingerprint=fingerprint,
                )
            )
            repository.log_event(
                AuditEvent(
                    trace_id=trace_id,
                    event_type="CAMPAIGN_PAUSED",
                    campaign_id=config.campaign_id,
                    payload={"stopped_at_iteration": iteration},
                )
            )
            return CampaignRunOutput(
                snapshot_fingerprint=fingerprint,
                batch_summaries=summaries,
                best_score=best_score,
                best_parameters=best_parameters,
            )

    repository.upsert_campaign(
        CampaignRecord(
            campaign_id=config.campaign_id,
            status=CampaignStatus.COMPLETED.value,
            snapshot_fingerprint=fingerprint,
        )
    )
    repository.log_event(
        AuditEvent(
            trace_id=trace_id,
            event_type="CAMPAIGN_FINISHED",
            campaign_id=config.campaign_id,
            payload={"best_score": best_score},
        )
    )
    return CampaignRunOutput(
        snapshot_fingerprint=fingerprint,
        batch_summaries=summaries,
        best_score=best_score,
        best_parameters=best_parameters,
    )
