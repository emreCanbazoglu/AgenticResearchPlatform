#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import time
from dataclasses import dataclass
from pathlib import Path

from core.multi_agent.director import Director
from core.multi_agent.worker_agent import CycleResult
from domains.polymarket.adapter import PolymarketRunResult, get_strategy
from domains.polymarket.base import MarketSnapshot
from domains.polymarket.data_store import HistoricalMarketStore, MarketRecord
from domains.polymarket.llm_evaluator import LLMEstimate, LLMEvaluator
from domains.polymarket.paper_session import PolymarketPaperConfig, PolymarketPaperSession
from domains.polymarket.worker import PolymarketWorkerAgent
from meta.optimizers.factory import make_optimizer

SAMPLE_DIR = Path("data/polymarket/sample")
PAPER_CHECKPOINT = "paper_polymarket.json"
TOTAL_BUDGET = 30_000.0
SEED = 42
PAPER_INTERVAL_SECONDS = 24 * 60 * 60

STRATEGY_ORDER = [
    "longshot_fade_v1",
    "momentum_v1",
    "mean_reversion_v1",
]


@dataclass
class StrategyBacktest:
    strategy_id: str
    cycle: CycleResult
    run_result: PolymarketRunResult
    by_category: dict[str, tuple[int, float]]
    avg_kelly: float
    best_bet: tuple[str, float, str, float] | None
    worst_bet: tuple[str, float, str, float] | None


def _pct(value: float) -> str:
    return f"{value:+.1%}"


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _load_snapshots(data_dir: Path) -> tuple[list[MarketSnapshot], list[float], list[MarketRecord]]:
    store = HistoricalMarketStore(data_dir)
    markets = store.load_all()

    snapshots: list[MarketSnapshot] = []
    outcomes: list[float] = []
    for market in markets:
        series = store.get_price_series(market.market_id)
        if not series:
            continue

        prices = [float(point.probability) for point in series]
        latest = series[-1]
        days_to_resolution = max(
            0.0,
            (market.resolved_at - latest.timestamp).total_seconds() / 86_400.0,
        )
        snapshots.append(
            MarketSnapshot(
                market_id=market.market_id,
                question=market.question,
                category=market.category,
                current_price=prices[-1],
                price_history=prices,
                days_to_resolution=days_to_resolution,
                tags=list(market.tags),
            )
        )
        outcomes.append(float(market.outcome))

    return snapshots, outcomes, markets


def _make_workers() -> list[PolymarketWorkerAgent]:
    workers: list[PolymarketWorkerAgent] = []
    for idx, strategy_id in enumerate(STRATEGY_ORDER):
        strategy = get_strategy(strategy_id)
        workers.append(
            PolymarketWorkerAgent(
                strategy_id=strategy_id,
                optimizer=make_optimizer("bayesian", search_space=strategy.search_space, seed=SEED + idx),
                seed=SEED + idx,
            )
        )
    return workers


def run_backtest(*, use_llm: bool = False, data_dir: Path = SAMPLE_DIR) -> list[StrategyBacktest]:
    snapshots, outcomes, _ = _load_snapshots(data_dir)
    workers = _make_workers()

    llm_estimates: list[LLMEstimate] = []
    if use_llm:
        evaluator = LLMEvaluator(api_key=os.getenv("ANTHROPIC_API_KEY"))
        llm_estimates = evaluator.batch_estimate(snapshots)
        for worker in workers:
            worker.set_llm_estimates(llm_estimates)

    for worker in workers:
        worker.self_tune(snapshots, outcomes, n_candidates=8)

    director = Director(total_budget=TOTAL_BUDGET, workers=workers)  # type: ignore[arg-type]
    allocations = director._allocate()

    summaries: list[StrategyBacktest] = []
    for worker in workers:
        cycle = worker.run_eval(
            eval_markets=snapshots,
            eval_outcomes=outcomes,
            budget=allocations.get(worker.strategy_id, 0.0),
            cycle_idx=0,
        )
        director._observe(worker.strategy_id, cycle.pnl_pct)

        run_result = worker._last_result
        if run_result is None:
            continue

        by_category = {
            category: (
                int(run_result.bets_by_category.get(category, 0)),
                float(run_result.profit_by_category.get(category, 0.0)),
            )
            for category in sorted(run_result.bets_by_category)
        }

        best: tuple[str, float, str, float] | None = None
        worst: tuple[str, float, str, float] | None = None
        if run_result.bet_records:
            best_record = max(run_result.bet_records, key=lambda item: item.profit)
            worst_record = min(run_result.bet_records, key=lambda item: item.profit)
            best = (
                best_record.question,
                float(best_record.profit),
                best_record.action.value.upper(),
                float(best_record.entry_price),
            )
            worst = (
                worst_record.question,
                float(worst_record.profit),
                worst_record.action.value.upper(),
                float(worst_record.entry_price),
            )

        summaries.append(
            StrategyBacktest(
                strategy_id=worker.strategy_id,
                cycle=cycle,
                run_result=run_result,
                by_category=by_category,
                avg_kelly=float(run_result.avg_kelly_fraction),
                best_bet=best,
                worst_bet=worst,
            )
        )

    return summaries


def print_backtest_report(*, use_llm: bool = False, data_dir: Path = SAMPLE_DIR) -> list[StrategyBacktest]:
    snapshots, _, markets = _load_snapshots(data_dir)
    summaries = run_backtest(use_llm=use_llm, data_dir=data_dir)

    if not summaries:
        print("No backtest results available.")
        return summaries

    start = min(item.resolved_at for item in markets).strftime("%b %Y")
    end = max(item.resolved_at for item in markets).strftime("%b %Y")

    print("━" * 60)
    print(f"POLYMARKET BACKTEST — {len(snapshots)} resolved markets ({start} – {end})")
    print("━" * 60)
    print()
    print("  Strategy             Bets   Win%    ROI     Avg Kelly")
    print("  ───────────────────────────────────────────────────────")
    for summary in summaries:
        print(
            f"  {summary.strategy_id:<20} "
            f"{summary.run_result.total_bets:>4}   "
            f"{summary.run_result.win_rate:>6.1%}  "
            f"{_pct(summary.run_result.roi):>7}   "
            f"{summary.avg_kelly:>8.1%}"
        )

    for summary in summaries:
        if not summary.by_category:
            continue
        print()
        print(f"  By category ({summary.strategy_id}):")
        for category, (bets, profit) in summary.by_category.items():
            roi = 0.0
            if summary.cycle.initial_equity > 0:
                roi = profit / summary.cycle.initial_equity
            print(f"    {category:<12}: {bets:>3} bets  {_pct(roi):>7}")

    best_candidates = [item.best_bet for item in summaries if item.best_bet is not None]
    worst_candidates = [item.worst_bet for item in summaries if item.worst_bet is not None]
    if best_candidates:
        question, profit, action, price = max(best_candidates, key=lambda item: item[1])
        print()
        print(f'  Best single bet: "{question}" — {_money(profit)} ({action} @ {price:.2f})')
    if worst_candidates:
        question, profit, action, price = min(worst_candidates, key=lambda item: item[1])
        print(f'  Worst single bet: "{question}" — {_money(profit)} ({action} @ {price:.2f})')

    print()
    print("━" * 60)
    return summaries


def _print_cycle(summary: object) -> None:
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")
    cycle_idx = int(getattr(summary, "cycle_idx", 0))
    total_budget_after = float(getattr(summary, "total_budget_after", 0.0))
    results = list(getattr(summary, "results", []))
    open_positions = sum(int(getattr(item, "trade_count", 0)) for item in results)
    print(
        f"Cycle {cycle_idx}  [{now}]  |  Cash: {_money(total_budget_after)}  "
        f"|  Open positions: {open_positions}  |  Resolved today: 0"
    )


def _make_paper_workers(use_llm: bool) -> list[PolymarketWorkerAgent]:
    workers = _make_workers()
    if use_llm:
        print("LLM priors are only applied in --backtest mode.")
    return workers


def _run_dry(session: PolymarketPaperSession) -> None:
    summary = session.run_one_cycle()
    _print_cycle(summary)
    payload = session.summary()
    print(
        f"Summary | cycles={payload['cycle_count']} cash={_money(payload['cash'])} "
        f"open_positions={payload['open_positions']} dry_run={payload['dry_run']}"
    )


def _run_paper_loop(session: PolymarketPaperSession) -> None:
    try:
        while True:
            summary = session.run_one_cycle()
            _print_cycle(summary)
            sleep_for = max(0, int(PAPER_INTERVAL_SECONDS))
            hours, rem = divmod(sleep_for, 3600)
            minutes = rem // 60
            print(f"Next cycle in {hours}h {minutes}m")
            time.sleep(sleep_for)
    except KeyboardInterrupt:
        session.save()
        print("\nStopped. Checkpoint saved.")


def _print_status(checkpoint_path: str = PAPER_CHECKPOINT) -> None:
    if not Path(checkpoint_path).exists():
        print(f"No checkpoint found at {checkpoint_path}")
        return

    workers = _make_paper_workers(use_llm=False)
    session = PolymarketPaperSession.load(checkpoint_path, workers)  # type: ignore[arg-type]
    payload = session.summary()
    print("Polymarket paper session status")
    print(f"  Checkpoint     : {checkpoint_path}")
    print(f"  Cycle count    : {payload['cycle_count']}")
    print(f"  Cash           : {_money(payload['cash'])}")
    print(f"  Open positions : {payload['open_positions']}")
    print(f"  Closed bets    : {payload['closed_positions']}")
    print(f"  Total profit   : {_money(payload['total_profit'])}")
    print(f"  ROI            : {_pct(payload['roi'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Polymarket workflows")
    parser.add_argument("--backtest", action="store_true", help="Run offline backtest on sample data")
    parser.add_argument("--dry-run", action="store_true", help="Run one live dry-run cycle (no bets saved)")
    parser.add_argument("--paper", action="store_true", help="Start live paper-trading loop")
    parser.add_argument("--status", action="store_true", help="Show paper session status")
    parser.add_argument("--llm", action="store_true", help="Enable LLM valuation layer (backtest only)")
    parser.add_argument("--data-dir", type=Path, default=SAMPLE_DIR, help="Market data directory (default: sample)")
    args = parser.parse_args()

    selected = [args.backtest, args.dry_run, args.paper, args.status]
    if sum(1 for item in selected if item) != 1:
        parser.error("choose exactly one mode: --backtest, --dry-run, --paper, or --status")

    if args.backtest:
        print_backtest_report(use_llm=args.llm, data_dir=args.data_dir)
        return

    if args.status:
        _print_status(PAPER_CHECKPOINT)
        return

    workers = _make_paper_workers(use_llm=args.llm)
    config = PolymarketPaperConfig(checkpoint_path=PAPER_CHECKPOINT, use_llm=args.llm)

    if args.dry_run:
        session = PolymarketPaperSession(config, workers, dry_run=True)  # type: ignore[arg-type]
        _run_dry(session)
        return

    session = (
        PolymarketPaperSession.load(PAPER_CHECKPOINT, workers)  # type: ignore[arg-type]
        if Path(PAPER_CHECKPOINT).exists()
        else PolymarketPaperSession(config, workers, dry_run=False)  # type: ignore[arg-type]
    )
    _run_paper_loop(session)


if __name__ == "__main__":
    main()
