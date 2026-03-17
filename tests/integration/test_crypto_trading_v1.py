from __future__ import annotations

import math
from pathlib import Path

from core.orchestration.campaign import CampaignConfig, run_campaign
from persistence.repositories import SqliteExperimentRepository


def _run_strategy(tmp_path: Path, strategy_id: str, run_idx: int):
    # Use the same campaign_id for both runs so the snapshot fingerprint is identical.
    campaign_id = f"crypto-v1-{strategy_id}"
    db_path = tmp_path / f"{strategy_id}-run-{run_idx}.sqlite"
    search_spaces: dict[str, dict[str, tuple[int, int]]] = {
        "ma_crossover_v1": {"fast_window": (2, 12), "slow_window": (13, 30)},
        "rsi_v1": {"period": (7, 21), "overbought": (60, 80), "oversold": (20, 40)},
        "macd_v1": {"fast_period": (4, 10), "slow_period": (20, 35), "signal_period": (5, 12)},
    }
    output = run_campaign(
        CampaignConfig(
            campaign_id=campaign_id,
            domain="trading",
            dataset_id="data/trading/btc_usdt_1d.csv",
            strategy_id=strategy_id,
            iterations=2,
            batch_size=4,
            seed=42,
            db_path=str(db_path),
            max_workers=2,
            search_space=search_spaces[strategy_id],
            optimizer="genetic",
        )
    )
    repo = SqliteExperimentRepository(str(db_path))
    completed_results = []
    for summary in output.batch_summaries:
        for result in repo.list_results_for_batch(summary.batch_id):
            if result.status == "COMPLETED":
                completed_results.append(result)
    return output, completed_results


def test_crypto_v1_all_strategies(tmp_path: Path) -> None:
    strategy_ids = ("ma_crossover_v1", "rsi_v1", "macd_v1")

    for strategy_id in strategy_ids:
        first_output, first_results = _run_strategy(tmp_path, strategy_id, 1)
        second_output, _ = _run_strategy(tmp_path, strategy_id, 2)

        assert math.isfinite(first_output.best_score)
        assert first_output.snapshot_fingerprint == second_output.snapshot_fingerprint
        assert first_output.best_score == second_output.best_score

        assert first_results
        for result in first_results:
            metrics = result.metrics
            assert "max_drawdown" in metrics
            assert "sharpe_ratio" in metrics
            assert "win_rate" in metrics
            assert "annualized_volatility" in metrics
            assert "commission_paid" in metrics
            assert 0.0 <= float(metrics["max_drawdown"]) <= 1.0
            assert 0.0 <= float(metrics["win_rate"]) <= 1.0
            assert float(metrics["commission_paid"]) >= 0.0
