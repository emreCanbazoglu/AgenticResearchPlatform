from __future__ import annotations

from core.orchestration.campaign import CampaignConfig, run_campaign


if __name__ == "__main__":
    output = run_campaign(
        CampaignConfig(
            campaign_id="demo-trading-mvp",
            domain="trading",
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="ma_crossover_v1",
            iterations=3,
            batch_size=8,
            seed=7,
            db_path="experiments.sqlite",
            max_workers=4,
            search_space={"fast_window": (2, 12), "slow_window": (8, 30)},
            optimizer="genetic",
        )
    )

    print("Snapshot:", output.snapshot_fingerprint)
    print("Best Score (profitability):", round(output.best_score, 6))
    print("Best Parameters:", output.best_parameters)
    for summary in output.batch_summaries:
        print(
            f"Batch {summary.iteration}: jobs={summary.candidate_count} "
            f"ok={summary.successful_count} best={summary.best_score:.6f}"
        )
