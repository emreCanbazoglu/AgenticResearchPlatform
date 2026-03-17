from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from core.multi_agent.worker_agent import CycleResult, WorkerAgent


@dataclass
class CycleSummary:
    cycle_idx: int
    total_budget_before: float
    total_budget_after: float
    allocations: dict[str, float]
    results: list[CycleResult]

    @property
    def best_worker(self) -> str:
        return max(self.results, key=lambda result: result.pnl_pct).strategy_id

    @property
    def pool_pnl_pct(self) -> float:
        if self.total_budget_before == 0:
            return 0.0
        return (self.total_budget_after - self.total_budget_before) / self.total_budget_before


@dataclass
class SessionResult:
    n_cycles: int
    initial_budget: float
    final_budget: float
    total_return_pct: float
    cycle_summaries: list[CycleSummary]
    final_allocations: dict[str, float]
    winner: str


class Director:
    def __init__(
        self,
        total_budget: float,
        workers: list[WorkerAgent],
        min_budget_fraction: float = 0.05,
        exploration_coeff: float = 1.0,
        max_tune_workers: int = 4,
        max_eval_workers: int = 4,
    ) -> None:
        self.total_budget = float(total_budget)
        self.workers = workers
        self.min_budget_fraction = float(min_budget_fraction)
        self.exploration_coeff = float(exploration_coeff)
        self.max_tune_workers = int(max_tune_workers)
        self.max_eval_workers = int(max_eval_workers)

        self.obs_count: dict[str, int] = {worker.strategy_id: 0 for worker in workers}
        self.sum_pnl_pct: dict[str, float] = {worker.strategy_id: 0.0 for worker in workers}
        self._cumulative_real_pnl: dict[str, float] = {worker.strategy_id: 0.0 for worker in workers}
        self._completed_cycles = 0

    def _allocate(self) -> dict[str, float]:
        if not self.workers:
            return {}

        strategy_ids = [worker.strategy_id for worker in self.workers]
        threshold = self.min_budget_fraction * self.total_budget

        unexplored = [sid for sid in strategy_ids if self.obs_count[sid] == 0]
        if unexplored:
            share = self.total_budget / len(unexplored) if unexplored else 0.0
            return {sid: (share if sid in unexplored else 0.0) for sid in strategy_ids}

        total_cycles = self._completed_cycles
        scores: dict[str, float] = {}
        for sid in strategy_ids:
            mean_pnl_pct = self.sum_pnl_pct[sid] / self.obs_count[sid]
            exploration = self.exploration_coeff * math.sqrt(
                math.log(total_cycles + 1) / (self.obs_count[sid] + 1)
            )
            scores[sid] = mean_pnl_pct + exploration

        positive_scores = {sid: max(0.0, score) for sid, score in scores.items()}
        score_total = sum(positive_scores.values())

        if score_total <= 0:
            tentative = {sid: self.total_budget / len(strategy_ids) for sid in strategy_ids}
        else:
            tentative = {
                sid: self.total_budget * (positive_scores[sid] / score_total)
                for sid in strategy_ids
            }

        active = {sid for sid, amount in tentative.items() if amount >= threshold}
        if not active:
            return {sid: 0.0 for sid in strategy_ids}

        active_total = sum(tentative[sid] for sid in active)
        if active_total <= 0:
            even = self.total_budget / len(active)
            return {sid: (even if sid in active else 0.0) for sid in strategy_ids}

        allocations = {
            sid: (self.total_budget * tentative[sid] / active_total if sid in active else 0.0)
            for sid in strategy_ids
        }
        return allocations

    def _observe(self, strategy_id: str, pnl_pct: float) -> None:
        self.obs_count[strategy_id] += 1
        self.sum_pnl_pct[strategy_id] += float(pnl_pct)

    def run_session(
        self,
        all_prices: list[float],
        cycle_size: int,
        lookback_size: int,
        n_tune_candidates: int = 8,
    ) -> SessionResult:
        n_cycles = (len(all_prices) - lookback_size) // cycle_size
        if n_cycles < 1:
            raise ValueError("not enough prices for even one cycle")

        initial_budget = self.total_budget
        cycle_summaries: list[CycleSummary] = []
        last_allocations: dict[str, float] = {}

        for cycle_idx in range(n_cycles):
            tune_end = cycle_idx * cycle_size
            tune_start = max(0, tune_end - lookback_size)
            eval_start = tune_end
            eval_end = eval_start + cycle_size

            tune_prices = all_prices[tune_start:tune_end]
            eval_prices = all_prices[eval_start:eval_end]

            with ThreadPoolExecutor(max_workers=self.max_tune_workers) as pool:
                futures = [
                    pool.submit(worker.self_tune, tune_prices, n_tune_candidates)
                    for worker in self.workers
                ]
                for future in futures:
                    future.result()

            allocations = self._allocate()
            last_allocations = dict(allocations)
            total_before = self.total_budget

            with ThreadPoolExecutor(max_workers=self.max_eval_workers) as pool:
                futures = {
                    worker.strategy_id: pool.submit(
                        worker.run_eval,
                        eval_prices,
                        allocations[worker.strategy_id],
                        cycle_idx,
                    )
                    for worker in self.workers
                }
                results = [futures[worker.strategy_id].result() for worker in self.workers]

            real_pnl = 0.0
            for result in results:
                if not result.is_virtual:
                    real_pnl += result.pnl
                    self._cumulative_real_pnl[result.strategy_id] += result.pnl

            self.total_budget += real_pnl

            for result in results:
                self._observe(result.strategy_id, result.pnl_pct)

            self._completed_cycles += 1
            cycle_summaries.append(
                CycleSummary(
                    cycle_idx=cycle_idx,
                    total_budget_before=total_before,
                    total_budget_after=self.total_budget,
                    allocations=allocations,
                    results=results,
                )
            )

        if self._cumulative_real_pnl:
            winner = max(
                sorted(self._cumulative_real_pnl),
                key=lambda sid: self._cumulative_real_pnl[sid],
            )
        else:
            winner = ""

        total_return_pct = 0.0
        if initial_budget != 0:
            total_return_pct = (self.total_budget - initial_budget) / initial_budget

        return SessionResult(
            n_cycles=n_cycles,
            initial_budget=initial_budget,
            final_budget=self.total_budget,
            total_return_pct=total_return_pct,
            cycle_summaries=cycle_summaries,
            final_allocations=last_allocations,
            winner=winner,
        )
