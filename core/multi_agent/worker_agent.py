from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domains.trading.adapter import TradingAdapter
from meta.optimizers.base import Optimizer


@dataclass
class CycleResult:
    strategy_id: str
    cycle_idx: int
    budget_allocated: float
    is_virtual: bool
    initial_equity: float
    final_equity: float
    pnl: float
    pnl_pct: float
    score: float
    params_used: dict[str, Any]
    trade_count: int
    commission_paid: float = 0.0
    slippage_paid: float = 0.0


@dataclass
class WorkerAgent:
    strategy_id: str
    search_space: dict[str, tuple[int, int]]
    optimizer: Optimizer
    seed: int
    virtual_budget: float = 10_000.0
    commission_rate: float = 0.001
    position_size_fraction: float = 1.0
    slippage_rate: float = 0.0

    _current_params: dict[str, Any] = field(default_factory=dict, init=False)
    _cycle_count: int = field(default=0, init=False)

    def _initialize_default_params(self) -> None:
        if self._current_params:
            return
        self._current_params = {
            key: int((bounds[0] + bounds[1]) // 2)
            for key, bounds in self.search_space.items()
        }

    def self_tune(self, prices: list[float], n_candidates: int = 8) -> None:
        self._initialize_default_params()
        if len(prices) < 20:
            return

        candidates = self.optimizer.suggest(iteration=self._cycle_count, batch_size=n_candidates)
        scored: list[tuple[Any, float]] = []

        for candidate in candidates:
            result = TradingAdapter(
                initial_capital=self.virtual_budget,
                commission_rate=self.commission_rate,
                position_size_fraction=self.position_size_fraction,
                slippage_rate=self.slippage_rate,
            ).run_on_prices(
                prices=prices,
                strategy_id=self.strategy_id,
                parameters=candidate.parameters,
                seed=self.seed,
            )
            scored.append((candidate, result.score))

        self.optimizer.observe(scored_candidates=scored)

        if scored:
            best_candidate = max(scored, key=lambda item: item[1])[0]
            self._current_params = dict(best_candidate.parameters)

        self._cycle_count += 1

    def run_eval(self, prices: list[float], budget: float, cycle_idx: int) -> CycleResult:
        self._initialize_default_params()

        is_virtual = budget <= 0
        actual_capital = self.virtual_budget if is_virtual else budget

        if len(prices) < 20:
            return CycleResult(
                strategy_id=self.strategy_id,
                cycle_idx=cycle_idx,
                budget_allocated=budget,
                is_virtual=is_virtual,
                initial_equity=actual_capital,
                final_equity=actual_capital,
                pnl=0.0,
                pnl_pct=0.0,
                score=0.0,
                params_used=dict(self._current_params),
                trade_count=0,
                commission_paid=0.0,
                slippage_paid=0.0,
            )

        result = TradingAdapter(
            initial_capital=actual_capital,
            commission_rate=self.commission_rate,
            position_size_fraction=self.position_size_fraction,
            slippage_rate=self.slippage_rate,
        ).run_on_prices(
            prices=prices,
            strategy_id=self.strategy_id,
            parameters=self._current_params,
            seed=self.seed,
        )

        final_equity = float(result.metrics["final_equity"])
        pnl = final_equity - actual_capital

        return CycleResult(
            strategy_id=self.strategy_id,
            cycle_idx=cycle_idx,
            budget_allocated=budget,
            is_virtual=is_virtual,
            initial_equity=actual_capital,
            final_equity=final_equity,
            pnl=pnl,
            pnl_pct=pnl / actual_capital,
            score=result.score,
            params_used=dict(self._current_params),
            trade_count=int(result.metrics["trade_count"]),
            commission_paid=float(result.metrics["commission_paid"]),
            slippage_paid=float(result.metrics["slippage_paid"]),
        )

    def checkpoint(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "current_params": dict(self._current_params),
            "cycle_count": self._cycle_count,
            "optimizer_state": self.optimizer.checkpoint(),
            "position_size_fraction": self.position_size_fraction,
            "slippage_rate": self.slippage_rate,
        }

    def restore(self, state: dict[str, Any]) -> None:
        self.strategy_id = str(state.get("strategy_id", self.strategy_id))
        self._current_params = dict(state.get("current_params", {}))
        self._cycle_count = int(state.get("cycle_count", 0))
        self.position_size_fraction = float(
            state.get("position_size_fraction", self.position_size_fraction)
        )
        self.slippage_rate = float(state.get("slippage_rate", self.slippage_rate))
        self.optimizer.restore(state.get("optimizer_state", {}))
