from __future__ import annotations

from pathlib import Path

from core.orchestration.campaign import CampaignConfig, run_campaign
from core.orchestration.resume import resume_from_checkpoint
from persistence.repositories import SqliteExperimentRepository


def test_campaign_can_resume_from_latest_checkpoint(tmp_path: Path) -> None:
    db_path = tmp_path / "resume.sqlite"
    campaign_id = "resume-campaign"

    partial = run_campaign(
        CampaignConfig(
            campaign_id=campaign_id,
            domain="trading",
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="ma_crossover_v1",
            iterations=3,
            batch_size=4,
            seed=17,
            db_path=str(db_path),
            max_workers=2,
            search_space={"fast_window": (2, 10), "slow_window": (8, 20)},
            optimizer="genetic",
            stop_after_iteration=0,
        )
    )
    assert len(partial.batch_summaries) == 1

    checkpoint = resume_from_checkpoint(str(db_path), campaign_id)
    assert checkpoint is not None
    assert checkpoint["iteration"] == 0

    resumed = run_campaign(
        CampaignConfig(
            campaign_id=campaign_id,
            domain="trading",
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="ma_crossover_v1",
            iterations=3,
            batch_size=4,
            seed=17,
            db_path=str(db_path),
            max_workers=2,
            search_space={"fast_window": (2, 10), "slow_window": (8, 20)},
            optimizer="genetic",
            resume_from_latest=True,
        )
    )

    repo = SqliteExperimentRepository(str(db_path))
    assert repo.get_campaign_status(campaign_id) == "COMPLETED"
    assert repo.get_batch_status(f"{campaign_id}-batch-000") in {"COMPLETED", "PARTIAL"}
    assert repo.get_batch_status(f"{campaign_id}-batch-001") in {"COMPLETED", "PARTIAL"}
    assert repo.get_batch_status(f"{campaign_id}-batch-002") in {"COMPLETED", "PARTIAL"}
    assert resumed.best_score >= partial.best_score
