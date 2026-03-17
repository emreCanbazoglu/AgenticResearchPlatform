from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Any

from domains.base import DomainRunResult
from domains.polymarket.base import BetAction, BettingStrategy, MarketSnapshot
from domains.polymarket.data_store import HistoricalMarketStore, MarketRecord
from domains.polymarket.strategies.longshot_fade import LongshotFadeStrategy
from domains.polymarket.strategies.mean_reversion import MeanReversionStrategy
from domains.polymarket.strategies.momentum import MomentumStrategy

if TYPE_CHECKING:
    from domains.polymarket.llm_evaluator import LLMEstimate


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def kelly_fraction(
    estimated_prob: float,
    market_price: float,
    confidence: float,
    max_fraction: float = 0.25,
) -> float:
    """
    Full Kelly fraction scaled by strategy confidence.

    Uses YES-side Kelly when estimated_prob >= market_price, and NO-side Kelly otherwise.
    Returns zero for invalid inputs or non-positive edge.
    """
    p_hat = _clamp01(float(estimated_prob))
    price = _clamp01(float(market_price))
    conf = _clamp01(float(confidence))
    max_frac = max(0.0, float(max_fraction))

    if not (0.0 < price < 1.0) or max_frac == 0.0 or conf == 0.0:
        return 0.0

    if p_hat >= price:
        raw_fraction = (p_hat - price) / (1.0 - price)
    else:
        raw_fraction = (price - p_hat) / price

    if raw_fraction <= 0.0:
        return 0.0

    return min(raw_fraction * conf, max_frac)


@dataclass
class BetRecord:
    market_id: str
    question: str
    category: str
    action: BetAction
    entry_price: float
    estimated_prob: float
    bet_amount: float
    shares: float
    outcome: float
    profit: float
    kelly_fraction: float


@dataclass
class PolymarketRunResult:
    final_equity: float
    initial_equity: float
    roi: float
    total_bets: int
    winning_bets: int
    win_rate: float
    total_profit: float
    avg_kelly_fraction: float
    bets_by_category: dict[str, int]
    profit_by_category: dict[str, float]
    bet_records: list[BetRecord]


_STRATEGY_REGISTRY: dict[str, BettingStrategy] = {
    "longshot_fade_v1": LongshotFadeStrategy(),
    "momentum_v1": MomentumStrategy(),
    "mean_reversion_v1": MeanReversionStrategy(),
}


def get_strategy(strategy_id: str) -> BettingStrategy:
    if strategy_id not in _STRATEGY_REGISTRY:
        raise ValueError(f"unknown strategy: {strategy_id}")
    return _STRATEGY_REGISTRY[strategy_id]


def _load_polymarket_scoring_weights(path: str = "config/scoring_polymarket.yaml") -> dict[str, float]:
    default_weights = {
        "roi": 0.50,
        "win_rate": 0.25,
        "drawdown": 0.15,
        "bet_count": 0.10,
    }

    config_path = Path(path)
    if not config_path.exists():
        return default_weights

    weights = dict(default_weights)
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = key.strip()
        if normalized_key not in default_weights:
            continue
        try:
            weights[normalized_key] = float(value.strip())
        except ValueError:
            continue

    return weights


def _max_losing_streak_fraction(profits: list[float]) -> float:
    if not profits:
        return 0.0

    max_streak = 0
    current_streak = 0
    for profit in profits:
        if profit < 0:
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
        else:
            current_streak = 0

    return max_streak / len(profits)


@dataclass
class PolymarketAdapter:
    initial_capital: float = 10_000.0
    max_kelly_fraction: float = 0.25
    min_market_liquidity: float = 1_000.0
    categories: list[str] = field(default_factory=list)

    def run(
        self,
        *,
        markets: list[MarketRecord],
        store: HistoricalMarketStore,
        strategy_id: str,
        parameters: dict[str, Any],
    ) -> PolymarketRunResult:
        sorted_markets = sorted(markets, key=lambda item: item.resolved_at)
        snapshots: list[MarketSnapshot] = []
        outcomes: list[float] = []

        for market in sorted_markets:
            if self.categories and market.category not in self.categories:
                continue

            # Current sample data has no liquidity field; when available, enforce threshold.
            liquidity = getattr(market, "liquidity", None)
            if isinstance(liquidity, (int, float)) and liquidity < self.min_market_liquidity:
                continue

            points = store.get_price_series(market.market_id)
            if not points:
                continue

            prices = [float(point.probability) for point in points]
            if not prices:
                continue

            latest_point = points[-1]
            days_to_resolution = max(
                0.0,
                (market.resolved_at - latest_point.timestamp).total_seconds() / 86_400.0,
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

        return self.run_on_snapshots(
            snapshots=snapshots,
            outcomes=outcomes,
            strategy_id=strategy_id,
            parameters=parameters,
        )

    def run_on_snapshots(
        self,
        *,
        snapshots: list[MarketSnapshot],
        outcomes: list[float],
        strategy_id: str,
        parameters: dict[str, Any],
        llm_estimates: dict[str, "LLMEstimate"] | None = None,
    ) -> PolymarketRunResult:
        if len(snapshots) != len(outcomes):
            raise ValueError("snapshots and outcomes must have same length")

        strategy = get_strategy(strategy_id)
        current_capital = float(self.initial_capital)
        records: list[BetRecord] = []
        bets_by_category: dict[str, int] = {}
        profit_by_category: dict[str, float] = {}
        winning_bets = 0
        kelly_values: list[float] = []

        for snapshot, raw_outcome in zip(snapshots, outcomes):
            outcome = 1.0 if float(raw_outcome) >= 0.5 else 0.0
            market_parameters = dict(parameters)
            if llm_estimates:
                llm_estimate = llm_estimates.get(snapshot.market_id)
                if llm_estimate is not None:
                    market_parameters["llm_prior"] = float(llm_estimate.estimated_probability)

            decision = strategy.evaluate(snapshot, market_parameters)

            if decision.action == BetAction.PASS:
                continue

            price = _clamp01(float(snapshot.current_price))
            estimated_prob = _clamp01(float(decision.estimated_probability))
            confidence = _clamp01(float(decision.confidence))

            if not (0.0 < price < 1.0):
                continue
            if decision.action == BetAction.BET_YES and estimated_prob <= price:
                continue
            if decision.action == BetAction.BET_NO and estimated_prob >= price:
                continue

            fraction = kelly_fraction(
                estimated_prob=estimated_prob,
                market_price=price,
                confidence=confidence,
                max_fraction=self.max_kelly_fraction,
            )
            if fraction <= 0.0:
                continue

            bet_amount = current_capital * fraction
            if bet_amount <= 0.0:
                continue

            shares = 0.0
            profit = 0.0
            if decision.action == BetAction.BET_YES:
                shares = bet_amount / price
                if outcome == 1.0:
                    profit = shares * (1.0 - price)
                else:
                    profit = -bet_amount
            elif decision.action == BetAction.BET_NO:
                no_price = 1.0 - price
                if no_price <= 0.0:
                    continue
                shares = bet_amount / no_price
                if outcome == 0.0:
                    profit = shares * price
                else:
                    profit = -bet_amount

            if not isfinite(profit):
                continue

            current_capital += profit
            if profit > 0:
                winning_bets += 1

            bets_by_category[snapshot.category] = bets_by_category.get(snapshot.category, 0) + 1
            profit_by_category[snapshot.category] = profit_by_category.get(snapshot.category, 0.0) + profit
            kelly_values.append(fraction)
            records.append(
                BetRecord(
                    market_id=snapshot.market_id,
                    question=snapshot.question,
                    category=snapshot.category,
                    action=decision.action,
                    entry_price=price,
                    estimated_prob=estimated_prob,
                    bet_amount=bet_amount,
                    shares=shares,
                    outcome=outcome,
                    profit=profit,
                    kelly_fraction=fraction,
                )
            )

        total_bets = len(records)
        total_profit = current_capital - self.initial_capital
        roi = 0.0 if self.initial_capital == 0 else total_profit / self.initial_capital
        win_rate = (winning_bets / total_bets) if total_bets > 0 else 0.0
        avg_kelly = (sum(kelly_values) / len(kelly_values)) if kelly_values else 0.0

        return PolymarketRunResult(
            final_equity=current_capital,
            initial_equity=self.initial_capital,
            roi=roi,
            total_bets=total_bets,
            winning_bets=winning_bets,
            win_rate=win_rate,
            total_profit=total_profit,
            avg_kelly_fraction=avg_kelly,
            bets_by_category=bets_by_category,
            profit_by_category=profit_by_category,
            bet_records=records,
        )

    def run_for_execution(
        self,
        *,
        dataset_id: str,
        strategy_id: str,
        parameters: dict[str, float],
        seed: int,
    ) -> DomainRunResult:
        del seed

        store = HistoricalMarketStore(dataset_id)
        run_result = self.run(
            markets=store.load_all(),
            store=store,
            strategy_id=strategy_id,
            parameters=parameters,
        )

        profit_series = [record.profit for record in run_result.bet_records]
        max_losing_streak_fraction = _max_losing_streak_fraction(profit_series)

        metrics = {
            "initial_equity": float(run_result.initial_equity),
            "final_equity": float(run_result.final_equity),
            "total_return": float(run_result.roi),
            "trade_count": float(run_result.total_bets),
            "win_rate": float(run_result.win_rate),
            "max_drawdown": float(max_losing_streak_fraction),
            "avg_kelly_fraction": float(run_result.avg_kelly_fraction),
        }

        weights = _load_polymarket_scoring_weights()
        normalized_roi = _clamp01((run_result.roi + 1.0) / 2.0)
        normalized_win_rate = _clamp01(run_result.win_rate)
        normalized_drawdown = _clamp01(max_losing_streak_fraction)
        normalized_bet_count = _clamp01(run_result.total_bets / 10.0)

        score = (
            weights["roi"] * normalized_roi
            + weights["win_rate"] * normalized_win_rate
            - weights["drawdown"] * normalized_drawdown
            + weights["bet_count"] * normalized_bet_count
        )

        return DomainRunResult(
            metrics=metrics,
            score=float(score),
            artifacts={
                "total_bets": str(run_result.total_bets),
                "winning_bets": str(run_result.winning_bets),
            },
        )
