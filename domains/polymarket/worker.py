from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.multi_agent.worker_agent import CycleResult
from domains.polymarket.adapter import PolymarketAdapter, PolymarketRunResult, get_strategy
from domains.polymarket.base import BetDecision, MarketSnapshot
from domains.polymarket.llm_evaluator import LLMEstimate
from meta.optimizers.base import Candidate, Optimizer


@dataclass
class PolymarketWorkerAgent:
    strategy_id: str
    optimizer: Optimizer
    seed: int
    virtual_budget: float = 10_000.0
    adapter: PolymarketAdapter = field(default_factory=PolymarketAdapter)

    _current_params: dict[str, Any] = field(default_factory=dict, init=False)
    _cycle_count: int = field(default=0, init=False)
    _last_result: PolymarketRunResult | None = field(default=None, init=False)
    _llm_estimates_by_market: dict[str, LLMEstimate] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.strategy = get_strategy(self.strategy_id)
        self.search_space = dict(self.strategy.search_space)

    def _initialize_default_params(self) -> None:
        if self._current_params:
            return
        self._current_params = dict(self.strategy.default_parameters)

    def _aggressive_fallback_candidate(self) -> Candidate:
        params = dict(self.strategy.default_parameters)
        params.update({key: bounds[0] for key, bounds in self.search_space.items()})
        if "threshold_high" in self.search_space:
            params["threshold_high"] = self.search_space["threshold_high"][0]
        if "max_price" in self.search_space:
            params["max_price"] = self.search_space["max_price"][1]
        if "reversion_strength" in self.search_space:
            low, high = self.search_space["reversion_strength"]
            params["reversion_strength"] = int((low + high) // 2)
        return Candidate(candidate_id=f"{self.strategy_id}-aggressive", parameters=params)

    def _sample_backtest_candidate(self) -> Candidate:
        params = dict(self.strategy.default_parameters)
        if self.strategy_id == "longshot_fade_v1":
            params.update({"threshold_low": 45, "threshold_high": 55, "min_confidence": 10, "llm_weight": 0})
        elif self.strategy_id == "momentum_v1":
            params.update(
                {"lookback_window": 3, "momentum_threshold": 2, "max_price": 95, "min_price": 5, "llm_weight": 0}
            )
        elif self.strategy_id == "mean_reversion_v1":
            params.update({"mean_window": 3, "deviation_threshold": 2, "reversion_strength": 50, "llm_weight": 0})
        return Candidate(candidate_id=f"{self.strategy_id}-sample-backtest", parameters=params)

    def set_llm_estimates(self, estimates: list[LLMEstimate]) -> None:
        self._llm_estimates_by_market = {item.market_id: item for item in estimates}

    def self_tune(
        self,
        training_markets: list[MarketSnapshot],
        training_outcomes: list[float],
        n_candidates: int = 8,
    ) -> None:
        self._initialize_default_params()
        if len(training_markets) < 3 or len(training_markets) != len(training_outcomes):
            return

        suggested = self.optimizer.suggest(iteration=self._cycle_count, batch_size=max(1, n_candidates))
        extras = [
            Candidate(candidate_id=f"{self.strategy_id}-default", parameters=dict(self.strategy.default_parameters)),
            self._aggressive_fallback_candidate(),
            self._sample_backtest_candidate(),
        ]
        candidates = suggested + extras
        scored: list[tuple[Candidate, float]] = []
        ranked: list[tuple[bool, int, float, Candidate]] = []

        for candidate in candidates:
            result = self.adapter.run_on_snapshots(
                snapshots=training_markets,
                outcomes=training_outcomes,
                strategy_id=self.strategy_id,
                parameters=candidate.parameters,
                llm_estimates=self._llm_estimates_by_market or None,
            )
            score = float(result.roi)
            scored.append((candidate, score))
            ranked.append((result.total_bets > 0, result.total_bets, score, candidate))

        self.optimizer.observe(scored_candidates=scored)
        if ranked:
            best = max(ranked, key=lambda item: (item[0], item[1], item[2]))[3]
            self._current_params = dict(best.parameters)

        self._cycle_count += 1

    def evaluate_market(self, snapshot: MarketSnapshot) -> BetDecision:
        self._initialize_default_params()
        merged = dict(self._current_params)
        llm = self._llm_estimates_by_market.get(snapshot.market_id)
        if llm is not None:
            merged["llm_prior"] = float(llm.estimated_probability)
        return self.strategy.evaluate(snapshot, merged)

    def run_eval(
        self,
        eval_markets: list[MarketSnapshot],
        eval_outcomes: list[float],
        budget: float,
        cycle_idx: int,
    ) -> CycleResult:
        self._initialize_default_params()

        is_virtual = budget <= 0
        actual_capital = float(self.virtual_budget if is_virtual else budget)

        if len(eval_markets) < 1 or len(eval_markets) != len(eval_outcomes):
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

        run_result = PolymarketAdapter(
            initial_capital=actual_capital,
            max_kelly_fraction=self.adapter.max_kelly_fraction,
            min_market_liquidity=self.adapter.min_market_liquidity,
            categories=list(self.adapter.categories),
        ).run_on_snapshots(
            snapshots=eval_markets,
            outcomes=eval_outcomes,
            strategy_id=self.strategy_id,
            parameters=self._current_params,
            llm_estimates=self._llm_estimates_by_market or None,
        )
        self._last_result = run_result

        pnl = run_result.final_equity - actual_capital
        pnl_pct = (pnl / actual_capital) if actual_capital > 0 else 0.0

        return CycleResult(
            strategy_id=self.strategy_id,
            cycle_idx=cycle_idx,
            budget_allocated=budget,
            is_virtual=is_virtual,
            initial_equity=actual_capital,
            final_equity=run_result.final_equity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            score=float(run_result.roi),
            params_used=dict(self._current_params),
            trade_count=int(run_result.total_bets),
            commission_paid=0.0,
            slippage_paid=0.0,
        )

    def checkpoint(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "current_params": dict(self._current_params),
            "cycle_count": self._cycle_count,
            "optimizer_state": self.optimizer.checkpoint(),
        }

    def restore(self, state: dict[str, Any]) -> None:
        self.strategy_id = str(state.get("strategy_id", self.strategy_id))
        self.strategy = get_strategy(self.strategy_id)
        self.search_space = dict(self.strategy.search_space)
        self._current_params = dict(state.get("current_params", {}))
        self._cycle_count = int(state.get("cycle_count", 0))
        self.optimizer.restore(state.get("optimizer_state", {}))
