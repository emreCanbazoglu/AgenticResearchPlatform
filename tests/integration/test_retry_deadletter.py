from __future__ import annotations

from pathlib import Path

from core.execution.dispatcher import dispatch_jobs
from persistence.models import ExperimentJob, ExperimentResult
from persistence.repositories import SqliteExperimentRepository


def test_failed_jobs_retry_then_deadletter(tmp_path: Path) -> None:
    repo = SqliteExperimentRepository(str(tmp_path / "retry.sqlite"))
    jobs = [
        ExperimentJob(
            job_id="bad-job-1",
            campaign_id="c-retry",
            batch_id="b-retry",
            candidate_id="cand-x",
            parent_candidate_id=None,
            domain="unknown-domain",
            dataset_id="na",
            strategy_id="na",
            parameters={},
            seed=1,
            priority="standard",
            attempt=1,
        )
    ]

    results = dispatch_jobs(
        jobs=jobs,
        repository=repo,
        max_workers=1,
        max_concurrent_per_campaign=1,
        max_attempts=3,
    )

    assert len(results) == 1
    assert results[0].status == "FAILED"
    assert results[0].attempt == 3
    assert repo.count_results() == 3
    assert repo.count_dead_letters() == 1


def test_result_insert_is_idempotent_per_attempt(tmp_path: Path) -> None:
    repo = SqliteExperimentRepository(str(tmp_path / "idempotent.sqlite"))
    result = ExperimentResult(
        job_id="j1",
        campaign_id="c1",
        batch_id="b1",
        attempt=1,
        status="COMPLETED",
        score=0.5,
        metrics={"m": 1.0},
        error=None,
    )

    first = repo.insert_result(result)
    second = repo.insert_result(result)

    assert first is True
    assert second is False
    assert repo.count_results() == 1


def test_timeout_retries_and_deadletters(tmp_path: Path) -> None:
    repo = SqliteExperimentRepository(str(tmp_path / "timeout.sqlite"))
    jobs = [
        ExperimentJob(
            job_id="slow-job-1",
            campaign_id="c-timeout",
            batch_id="b-timeout",
            candidate_id="cand-slow",
            parent_candidate_id=None,
            domain="trading",
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="ma_crossover_v1",
            parameters={"fast_window": 4, "slow_window": 8, "_delay_seconds": 0.2},
            seed=1,
            trace_id="trace-timeout",
            priority="standard",
            attempt=1,
        )
    ]

    results = dispatch_jobs(
        jobs=jobs,
        repository=repo,
        max_workers=1,
        max_concurrent_per_campaign=1,
        max_attempts=2,
        job_timeout_seconds=0.01,
    )

    assert len(results) == 1
    assert results[0].status == "FAILED"
    assert results[0].attempt == 2
    assert "lease_timeout" in (results[0].error or "")
    assert repo.count_results() == 2
    assert repo.count_dead_letters() == 1
