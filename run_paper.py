#!/usr/bin/env python3
"""Live paper-trading loop that evaluates one 30m cycle at each UTC boundary."""

from __future__ import annotations

import argparse
import datetime
import time
from pathlib import Path
from typing import Any

from core.multi_agent.director import CycleSummary
from core.multi_agent.paper_session import PaperSession, PaperSessionConfig
from core.multi_agent.worker_agent import WorkerAgent
from meta.optimizers.factory import make_optimizer

SYMBOL = "BTCUSDT"
INTERVAL = "30m"
CYCLE_SIZE = 6  # 3 hours of bars per eval — richer trade signal than 1-candle evals
LOOKBACK_SIZE = 200
N_TUNE_CANDIDATES = 8
TOTAL_BUDGET = 30_000.0
CHECKPOINT_PATH = "paper_session.json"
SEED = 42

# Realistic microstructure defaults
POSITION_SIZE_FRACTION = 0.95
SLIPPAGE_RATE = 0.0005


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
            position_size_fraction=POSITION_SIZE_FRACTION,
            slippage_rate=SLIPPAGE_RATE,
        ),
        WorkerAgent(
            strategy_id="rsi_v1",
            search_space=rsi_space,
            optimizer=make_optimizer("bayesian", search_space=rsi_space, seed=SEED + 1),
            seed=SEED + 1,
            virtual_budget=10_000.0,
            position_size_fraction=POSITION_SIZE_FRACTION,
            slippage_rate=SLIPPAGE_RATE,
        ),
        WorkerAgent(
            strategy_id="macd_v1",
            search_space=macd_space,
            optimizer=make_optimizer("bayesian", search_space=macd_space, seed=SEED + 2),
            seed=SEED + 2,
            virtual_budget=10_000.0,
            position_size_fraction=POSITION_SIZE_FRACTION,
            slippage_rate=SLIPPAGE_RATE,
        ),
    ]


def sleep_until_next_boundary(interval_minutes: int = 30) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    minutes_past = now.minute % interval_minutes
    seconds_past = minutes_past * 60 + now.second
    wait = interval_minutes * 60 - seconds_past
    next_time = now + datetime.timedelta(seconds=wait)
    print(f"  Next cycle in {wait}s  (at {next_time.strftime('%H:%M')} UTC)")
    time.sleep(wait)


def print_cycle(summary: CycleSummary, cycle_count: int) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
    width = max(2, len(str(cycle_count)))
    print(
        f"Cycle {cycle_count:>{width}d}  [{ts} UTC]  "
        f"│  Pool: {_money(summary.total_budget_before)} → {_money(summary.total_budget_after)}  "
        f"({_pct(summary.pool_pnl_pct)})"
    )

    for result in summary.results:
        strategy_name = _display_strategy_id(result.strategy_id)
        mode = "virtual" if result.is_virtual else "real"
        print(
            "          "
            "│   "
            f"{strategy_name:<12}  "
            f"{_money(result.final_equity):>10}   "
            f"{_pct(result.pnl_pct):>7}  "
            f"[{mode}]   "
            f"{_format_params(result.strategy_id, result.params_used)}"
        )


def print_header(session: PaperSession, config: PaperSessionConfig) -> None:
    cycle_count = session.summary()["cycle_count"]
    if cycle_count > 0:
        checkpoint_text = f"resumed from cycle {cycle_count}"
    else:
        checkpoint_text = "cycle 0 — fresh start"

    print(f"Paper Trading Session — {config.symbol} {config.interval}")
    print(f"Checkpoint : {config.checkpoint_path}  ({checkpoint_text})")
    print(f"Budget     : {_money(config.total_budget)}  |  Workers: {len(session.workers)}")
    print(f"Cycle size : {config.cycle_size} candle  |  Lookback: {config.lookback_size} candles")
    print(
        f"Slippage   : {SLIPPAGE_RATE * 10_000:.1f} bps per fill  |  "
        f"Position size: {POSITION_SIZE_FRACTION:.0%} of allocated budget"
    )
    print("━" * 60)


def print_final_summary(session: PaperSession) -> None:
    payload = session.summary()
    total_commission = sum(
        result.commission_paid
        for cycle in session._history
        for result in cycle.results
        if not result.is_virtual
    )
    total_slippage = sum(
        result.slippage_paid
        for cycle in session._history
        for result in cycle.results
        if not result.is_virtual
    )

    print("━" * 60)
    print("SESSION SUMMARY")
    print(f"  Initial pool  :  {_money(payload['initial_budget'])}")
    print(f"  Final pool    :  {_money(payload['current_budget'])}")
    print(f"  Total return  :  {_pct(payload['total_return_pct'])}")
    print(f"  Cycles run    :  {payload['cycle_count']}")
    print(f"  Winner        :  {payload['best_worker']}  (highest cumulative real P&L)")
    print("  Cost breakdown (across all real cycles):")
    print(f"    Total commission paid  :  {_money(total_commission)}")
    print(f"    Total slippage paid    :  {_money(total_slippage)}")
    print(f"    Total friction         :  {_money(total_commission + total_slippage)}")
    print()
    print("  Final parameters (best found):")
    for worker in session.workers:
        params = worker.checkpoint().get("current_params", {})
        print(f"    {worker.strategy_id:<16} :  {_format_params(worker.strategy_id, params)}")


def _load_or_create_session(config: PaperSessionConfig, workers: list[WorkerAgent]) -> PaperSession:
    if Path(config.checkpoint_path).exists():
        return PaperSession.load(config.checkpoint_path, workers)
    return PaperSession(config, workers)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live paper-trading session")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run one immediate cycle using live candles, then exit",
    )
    args = parser.parse_args()

    config = PaperSessionConfig(
        symbol=SYMBOL,
        interval=INTERVAL,
        cycle_size=CYCLE_SIZE,
        lookback_size=LOOKBACK_SIZE,
        n_tune_candidates=N_TUNE_CANDIDATES,
        checkpoint_path=CHECKPOINT_PATH,
        total_budget=TOTAL_BUDGET,
    )
    workers = _make_workers()
    session = _load_or_create_session(config, workers)

    print_header(session, config)

    if args.dry_run:
        summary = session.run_one_cycle()
        session.save()
        print_cycle(summary, session.summary()["cycle_count"])
        print_final_summary(session)
        return

    try:
        while True:
            sleep_until_next_boundary(30)
            summary = session.run_one_cycle()
            try:
                session.save()
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] checkpoint save failed: {exc}")
            print_cycle(summary, session.summary()["cycle_count"])
    except KeyboardInterrupt:
        session.save()
        print("\n\nSession interrupted. Final state saved.")
        print_final_summary(session)


if __name__ == "__main__":
    main()
