from __future__ import annotations

from pathlib import Path

from core.orchestration.campaign import CampaignConfig, run_campaign
from persistence.repositories import SqliteExperimentRepository


def test_campaign_emits_traceable_audit_events(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.sqlite"
    campaign_id = "audit-campaign"

    run_campaign(
        CampaignConfig(
            campaign_id=campaign_id,
            domain="trading",
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="ma_crossover_v1",
            iterations=1,
            batch_size=3,
            seed=5,
            db_path=str(db_path),
            max_workers=2,
            search_space={"fast_window": (2, 10), "slow_window": (8, 20)},
            optimizer="genetic",
        )
    )

    repo = SqliteExperimentRepository(str(db_path))
    events = repo.list_events(campaign_id)

    assert len(events) > 0
    event_types = {event["event_type"] for event in events}
    assert "CAMPAIGN_STARTED" in event_types
    assert "BATCH_STARTED" in event_types
    assert "JOB_QUEUED" in event_types
    assert "JOB_STARTED" in event_types
    assert "CAMPAIGN_FINISHED" in event_types

    trace_ids = {event["trace_id"] for event in events}
    assert len(trace_ids) == 1
