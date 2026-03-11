from __future__ import annotations

from pathlib import Path

from core.orchestration.campaign import CampaignConfig, run_campaign


def _run(tmp_path: Path, suffix: str):
    return run_campaign(
        CampaignConfig(
            campaign_id="det-campaign",
            domain="trading",
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="ma_crossover_v1",
            iterations=2,
            batch_size=6,
            seed=42,
            db_path=str(tmp_path / f"{suffix}.sqlite"),
            max_workers=2,
            search_space={"fast_window": (2, 10), "slow_window": (8, 20)},
        )
    )


def test_campaign_is_deterministic(tmp_path: Path) -> None:
    first = _run(tmp_path, "one")
    second = _run(tmp_path, "two")

    assert first.snapshot_fingerprint == second.snapshot_fingerprint
    assert first.best_score == second.best_score
    assert first.best_parameters == second.best_parameters
    assert first.batch_summaries == second.batch_summaries
