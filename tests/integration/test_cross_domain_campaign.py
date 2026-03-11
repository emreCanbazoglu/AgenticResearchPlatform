from __future__ import annotations

from pathlib import Path

from core.orchestration.campaign import CampaignConfig, run_campaign


def test_orchestrator_runs_trading_and_game_economy_domains(tmp_path: Path) -> None:
    trading_db = tmp_path / "trading.sqlite"
    economy_db = tmp_path / "economy.sqlite"

    trading_out = run_campaign(
        CampaignConfig(
            campaign_id="cross-domain-trading",
            domain="trading",
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="ma_crossover_v1",
            iterations=1,
            batch_size=4,
            seed=21,
            db_path=str(trading_db),
            max_workers=2,
            search_space={"fast_window": (2, 10), "slow_window": (8, 20)},
            optimizer="genetic",
        )
    )

    economy_out = run_campaign(
        CampaignConfig(
            campaign_id="cross-domain-economy",
            domain="game_economy",
            dataset_id="economy-sim-v1",
            strategy_id="economy_balancer_v1",
            iterations=1,
            batch_size=4,
            seed=21,
            db_path=str(economy_db),
            max_workers=2,
            search_space={"reward_multiplier": (1, 3), "sink_multiplier": (1, 3)},
            optimizer="bayesian",
        )
    )

    assert trading_out.best_score > 0.0
    assert economy_out.best_score <= 0.0
    assert "fast_window" in trading_out.best_parameters
    assert "reward_multiplier" in economy_out.best_parameters
    assert trading_out.snapshot_fingerprint != economy_out.snapshot_fingerprint
