from __future__ import annotations

from pathlib import Path

from core.orchestration.campaign import CampaignConfig, run_campaign
from persistence.repositories import SqliteExperimentRepository


def test_trading_campaign_runs_and_scores_profitability(tmp_path: Path) -> None:
    db_path = tmp_path / "mvp.sqlite"
    output = run_campaign(
        CampaignConfig(
            campaign_id="mvp-integration",
            domain="trading",
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="ma_crossover_v1",
            iterations=2,
            batch_size=5,
            seed=9,
            db_path=str(db_path),
            max_workers=2,
            search_space={"fast_window": (2, 10), "slow_window": (8, 20)},
        )
    )

    assert output.best_score > 0.0
    repo = SqliteExperimentRepository(str(db_path))
    assert repo.count_results() == 10
