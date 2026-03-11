from __future__ import annotations

from pathlib import Path

from core.orchestration.campaign import CampaignConfig, run_campaign
from persistence.repositories import SqliteExperimentRepository


def test_audit_and_lineage_integrity_for_campaign(tmp_path: Path) -> None:
    db_path = tmp_path / "audit_lineage.sqlite"
    campaign_id = "audit-lineage-campaign"

    run_campaign(
        CampaignConfig(
            campaign_id=campaign_id,
            domain="trading",
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="ma_crossover_v1",
            iterations=1,
            batch_size=5,
            seed=31,
            db_path=str(db_path),
            max_workers=2,
            search_space={"fast_window": (2, 10), "slow_window": (8, 20)},
            optimizer="genetic",
        )
    )

    repo = SqliteExperimentRepository(str(db_path))
    events = repo.list_events(campaign_id)

    assert len(events) > 0
    trace_ids = {event["trace_id"] for event in events}
    assert len(trace_ids) == 1

    queued_jobs = {event["job_id"] for event in events if event["event_type"] == "JOB_QUEUED"}
    started_jobs = {event["job_id"] for event in events if event["event_type"] == "JOB_STARTED"}
    completed_jobs = {event["job_id"] for event in events if event["event_type"] == "JOB_COMPLETED"}
    assert queued_jobs == started_jobs == completed_jobs

    assert repo.count_lineage_records() == len(queued_jobs)
