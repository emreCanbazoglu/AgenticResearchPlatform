from __future__ import annotations

from pathlib import Path

from core.orchestration.campaign import CampaignConfig, run_campaign
from persistence.repositories import SqliteExperimentRepository


def test_campaign_and_batch_status_are_persisted(tmp_path: Path) -> None:
    db_path = tmp_path / "lifecycle.sqlite"
    campaign_id = "lifecycle-campaign"

    run_campaign(
        CampaignConfig(
            campaign_id=campaign_id,
            domain="trading",
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="ma_crossover_v1",
            iterations=2,
            batch_size=3,
            seed=13,
            db_path=str(db_path),
            max_workers=2,
            search_space={"fast_window": (2, 10), "slow_window": (8, 20)},
        )
    )

    repo = SqliteExperimentRepository(str(db_path))
    assert repo.get_campaign_status(campaign_id) == "COMPLETED"
    assert repo.get_batch_status(f"{campaign_id}-batch-000") in {"COMPLETED", "PARTIAL"}
    assert repo.get_batch_status(f"{campaign_id}-batch-001") in {"COMPLETED", "PARTIAL"}
