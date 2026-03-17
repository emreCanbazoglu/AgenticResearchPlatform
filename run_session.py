#!/usr/bin/env python3
"""
Multi-agent trading session.

Three strategy workers (MA crossover, RSI, MACD) compete for a shared $30,000
budget over rolling 30-minute cycles on real BTC data.
The Director reallocates capital each cycle using UCB1 - winners get more,
losers run on virtual capital until they recover.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from core.multi_agent.director import Director, SessionResult
from core.multi_agent.worker_agent import WorkerAgent
from meta.optimizers.factory import make_optimizer

DATASET = "data/trading/btc_usdt_30m.csv"
FALLBACK_DATA = "data/trading/btc_usdt_1d.csv"  # used if 30m file missing
TOTAL_BUDGET = 30_000.0
SEED = 42
CYCLE_SIZE = 48  # candles per cycle (~1 trading day at 30m)
LOOKBACK_SIZE = 200  # candles for tuning window
N_TUNE_CANDS = 8  # candidates per optimizer call per tune phase
MIN_BUDGET_PCT = 0.05  # workers below 5% of pool run virtually
EXPLORATION_C = 1.0  # UCB1 exploration coefficient


def _load_prices() -> tuple[list[float], str]:
    primary = Path(DATASET)
    fallback = Path(FALLBACK_DATA)
    dataset = primary

    if not primary.exists():
        dataset = fallback
        print(f"WARNING: dataset not found at {DATASET}; using fallback {FALLBACK_DATA}")

    with dataset.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        prices = [float(row["close"]) for row in reader]

    return prices, str(dataset)


def _make_workers() -> list[WorkerAgent]:
    ma_space = {"fast_window": (2, 20), "slow_window": (5, 60)}
    rsi_space = {"period": (5, 30), "overbought": (60, 80), "oversold": (20, 40)}
    macd_space = {"fast_period": (5, 15), "slow_period": (20, 40), "signal_period": (5, 15)}

    return [
        WorkerAgent(
            strategy_id="ma_crossover_v1",
            search_space=ma_space,
            optimizer=make_optimizer("bayesian", search_space=ma_space, seed=SEED),
            seed=SEED,
            virtual_budget=10_000.0,
            position_size_fraction=0.95,
            slippage_rate=0.0005,
        ),
        WorkerAgent(
            strategy_id="rsi_v1",
            search_space=rsi_space,
            optimizer=make_optimizer("bayesian", search_space=rsi_space, seed=SEED + 1),
            seed=SEED + 1,
            virtual_budget=10_000.0,
            position_size_fraction=0.95,
            slippage_rate=0.0005,
        ),
        WorkerAgent(
            strategy_id="macd_v1",
            search_space=macd_space,
            optimizer=make_optimizer("bayesian", search_space=macd_space, seed=SEED + 2),
            seed=SEED + 2,
            virtual_budget=10_000.0,
            position_size_fraction=0.95,
            slippage_rate=0.0005,
        ),
    ]


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _pct(value: float) -> str:
    return f"{value:+.2%}"


def _display_strategy_id(strategy_id: str) -> str:
    if strategy_id == "ma_crossover_v1":
        return "ma_crossover"
    return strategy_id


def _format_params(strategy_id: str, params: dict[str, Any]) -> str:
    if strategy_id == "ma_crossover_v1":
        return (
            f"fast={int(params.get('fast_window', 0))} "
            f"slow={int(params.get('slow_window', 0))}"
        )
    if strategy_id == "rsi_v1":
        return (
            f"period={int(params.get('period', 0))} "
            f"ob={int(params.get('overbought', 0))} "
            f"os={int(params.get('oversold', 0))}"
        )
    if strategy_id == "macd_v1":
        return (
            f"fast={int(params.get('fast_period', 0))} "
            f"slow={int(params.get('slow_period', 0))} "
            f"sig={int(params.get('signal_period', 0))}"
        )

    pairs = [f"{key}={value}" for key, value in sorted(params.items())]
    return " ".join(pairs)


def _print_cycle(cycle_idx: int, total_cycles: int, cycle_results: SessionResult) -> None:
    cycle = cycle_results.cycle_summaries[cycle_idx]
    print(
        f"Cycle {cycle.cycle_idx:>{len(str(total_cycles - 1))}d}  "
        f"| Pool: {_money(cycle.total_budget_before)} -> {_money(cycle.total_budget_after)}  "
        f"({_pct(cycle.pool_pnl_pct)})"
    )
    for result in cycle.results:
        strategy_name = _display_strategy_id(result.strategy_id)
        mode = "virtual" if result.is_virtual else "real"
        print(
            "           "
            f"|   {strategy_name:<12}  "
            f"{_money(result.budget_allocated):>10}  "
            f"{_pct(result.pnl_pct):>7}  "
            f"[{mode}]   "
            f"params: {_format_params(result.strategy_id, result.params_used)}"
        )


def _print_summary(session: SessionResult, workers: list[WorkerAgent]) -> None:
    total_commission = sum(
        result.commission_paid
        for cycle in session.cycle_summaries
        for result in cycle.results
        if not result.is_virtual
    )
    total_slippage = sum(
        result.slippage_paid
        for cycle in session.cycle_summaries
        for result in cycle.results
        if not result.is_virtual
    )

    print("━" * 60)
    print("SESSION SUMMARY")
    print(f"  Initial pool  :  {_money(session.initial_budget)}")
    print(f"  Final pool    :  {_money(session.final_budget)}")
    print(f"  Total return  :  {_pct(session.total_return_pct)}")
    print(f"  Cycles run    :  {session.n_cycles}")
    print(f"  Winner        :  {session.winner}  (highest cumulative real P&L)")
    print("  Cost breakdown (across all real cycles):")
    print(f"    Total commission paid  :  {_money(total_commission)}")
    print(f"    Total slippage paid    :  {_money(total_slippage)}")
    print(f"    Total friction         :  {_money(total_commission + total_slippage)}")
    print()
    print("  Final parameters (best found):")
    for worker in workers:
        params = worker.checkpoint().get("current_params", {})
        print(f"    {worker.strategy_id:<16} :  {_format_params(worker.strategy_id, params)}")


def main() -> None:
    prices, dataset_used = _load_prices()
    workers = _make_workers()
    director = Director(
        total_budget=TOTAL_BUDGET,
        workers=workers,
        min_budget_fraction=MIN_BUDGET_PCT,
        exploration_coeff=EXPLORATION_C,
    )
    session = director.run_session(
        all_prices=prices,
        cycle_size=CYCLE_SIZE,
        lookback_size=LOOKBACK_SIZE,
        n_tune_candidates=N_TUNE_CANDS,
    )

    print("Multi-Agent Session - BTC/USDT 30m")
    print(f"Dataset : {dataset_used}  ({len(prices)} candles)")
    print(
        f"Budget  : {_money(TOTAL_BUDGET)}  |  Workers: {len(workers)}  |  "
        f"Cycles: {session.n_cycles}"
    )
    print(f"Cycle size: {CYCLE_SIZE} candles  |  Lookback: {LOOKBACK_SIZE} candles")
    print("━" * 60)

    for cycle_idx in range(session.n_cycles):
        _print_cycle(cycle_idx, session.n_cycles, session)

    _print_summary(session, workers)


if __name__ == "__main__":
    main()
