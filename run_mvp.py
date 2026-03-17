from __future__ import annotations

from core.execution import adapters as adapter_registry
from core.execution import worker as worker_module
from core.orchestration.campaign import CampaignConfig, CampaignRunOutput, run_campaign
from domains.trading.adapter import TradingAdapter

_ORIGINAL_GET_ADAPTER = adapter_registry.get_adapter

ITERATIONS = 15      # 15 × 8 = 120 evaluations — enough for Bayesian warm-up + exploitation
BATCH_SIZE = 8
SEED = 7
DB_PATH = "experiments.sqlite"

# Search space: fast and slow MA windows for daily BTC data
SEARCH_SPACE = {"fast_window": (2, 20), "slow_window": (5, 60)}


def _mvp_get_adapter(domain: str):
    if domain == "trading":
        return TradingAdapter(train_ratio=0.7)
    return _ORIGINAL_GET_ADAPTER(domain)


def _run(optimizer: str) -> CampaignRunOutput:
    return run_campaign(
        CampaignConfig(
            campaign_id=f"btc-ma-{optimizer}-v1",
            domain="trading",
            dataset_id="data/trading/btc_usdt_1d.csv",
            strategy_id="ma_crossover_v1",
            iterations=ITERATIONS,
            batch_size=BATCH_SIZE,
            seed=SEED,
            db_path=DB_PATH,
            max_workers=4,
            search_space=SEARCH_SPACE,
            optimizer=optimizer,
        )
    )


def _print_convergence(label: str, output: CampaignRunOutput) -> None:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Best composite score : {output.best_score:.6f}")
    print(f"  Best parameters      : fast={int(output.best_parameters.get('fast_window', 0))}d  "
          f"slow={int(output.best_parameters.get('slow_window', 0))}d")
    print()
    print(f"  {'Iter':>4}  {'Candidates':>10}  {'OK':>4}  {'Batch Best':>12}  {'Running Best':>13}")
    print(f"  {'-'*4}  {'-'*10}  {'-'*4}  {'-'*12}  {'-'*13}")
    running_best = float("-inf")
    for s in output.batch_summaries:
        running_best = max(running_best, s.best_score)
        print(f"  {s.iteration:>4}  {s.candidate_count:>10}  {s.successful_count:>4}  "
              f"{s.best_score:>12.6f}  {running_best:>13.6f}")


if __name__ == "__main__":
    adapter_registry.get_adapter = _mvp_get_adapter
    worker_module.get_adapter = _mvp_get_adapter

    optimizers = ["genetic", "bayesian", "bandit"]
    results: dict[str, CampaignRunOutput] = {}

    print(f"\nRunning {len(optimizers)} campaigns × {ITERATIONS} iterations × {BATCH_SIZE} candidates")
    print(f"Dataset : data/trading/btc_usdt_1d.csv  (1000 real daily candles)")
    print(f"Strategy: MA Crossover  |  Walk-forward split: 70% train / 30% test")
    print(f"Search space: fast_window {SEARCH_SPACE['fast_window']}  "
          f"slow_window {SEARCH_SPACE['slow_window']}")

    for opt in optimizers:
        print(f"\n>>> Running {opt} optimizer...")
        results[opt] = _run(opt)

    # --- Summary comparison ---
    print(f"\n\n{'#'*60}")
    print(f"  OPTIMIZER COMPARISON — BTC/USDT Daily MA Crossover")
    print(f"  {ITERATIONS} iterations × {BATCH_SIZE} batch = {ITERATIONS * BATCH_SIZE} evaluations each")
    print(f"  Score = composite (40% return, 40% Sharpe, 20% drawdown) on TEST split")
    print(f"{'#'*60}")
    print(f"\n  {'Optimizer':>10}  {'Best Score':>12}  {'fast_window':>11}  {'slow_window':>11}")
    print(f"  {'-'*10}  {'-'*12}  {'-'*11}  {'-'*11}")
    for opt, output in results.items():
        fw = int(output.best_parameters.get("fast_window", 0))
        sw = int(output.best_parameters.get("slow_window", 0))
        print(f"  {opt:>10}  {output.best_score:>12.6f}  {fw:>11}  {sw:>11}")

    for opt, output in results.items():
        _print_convergence(f"{opt.upper()} convergence", output)
