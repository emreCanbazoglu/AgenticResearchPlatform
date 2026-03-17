from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from domains.base import DomainRunResult
from domains.trading.strategies.macd import MACDStrategy
from domains.trading.strategies.moving_average import MovingAverageCrossover
from domains.trading.strategies.rsi import RSIStrategy
from scoring.metrics import (
    annualized_volatility,
    composite_score,
    load_scoring_weights,
    max_drawdown,
    profitability_score,
    sharpe_ratio,
    win_rate,
)


class SignalStrategy(Protocol):
    def signal(self, prices: list[float], idx: int) -> int:
        ...


StrategyRunOutput = tuple[float, int, list[float], list[float], float, float]
StrategyRunner = Callable[[list[float], dict[str, float]], StrategyRunOutput]


def _run_backtest(
    *,
    prices: list[float],
    strategy: SignalStrategy,
    initial_capital: float,
    commission_rate: float = 0.0,
    position_size_fraction: float = 1.0,
    slippage_rate: float = 0.0,
) -> StrategyRunOutput:
    cash = initial_capital
    position = 0.0
    buy_cost: float | None = None
    trade_count = 0
    total_commission = 0.0
    total_slippage = 0.0
    equity_curve: list[float] = []
    trade_pnls: list[float] = []

    for i, price in enumerate(prices):
        signal = strategy.signal(prices, i)

        if signal > 0 and position == 0.0:
            invest_amount = cash * position_size_fraction
            exec_price = price * (1.0 + slippage_rate)
            slippage_cost = invest_amount * slippage_rate
            commission_cost = invest_amount * commission_rate
            cash_spent = invest_amount
            units = (invest_amount - commission_cost - slippage_cost) / exec_price
            position = units
            cash -= cash_spent
            buy_cost = invest_amount
            total_commission += commission_cost
            total_slippage += slippage_cost
            trade_count += 1
        elif signal < 0 and position > 0.0:
            exec_price = price * (1.0 - slippage_rate)
            gross_proceeds = position * exec_price
            slippage_cost = position * price * slippage_rate
            commission_cost = gross_proceeds * commission_rate
            net_proceeds = gross_proceeds - commission_cost
            total_commission += commission_cost
            total_slippage += slippage_cost
            cash += net_proceeds
            if buy_cost is not None:
                trade_pnls.append(net_proceeds - buy_cost)
            position = 0.0
            buy_cost = None
            trade_count += 1

        equity_curve.append(cash + position * price)

    final_equity = cash + position * prices[-1]
    return final_equity, trade_count, equity_curve, trade_pnls, total_commission, total_slippage


def _run_ma_crossover(prices: list[float], parameters: dict[str, float]) -> StrategyRunOutput:
    fast_window = int(parameters["fast_window"])
    slow_window = int(parameters["slow_window"])
    if fast_window < 2 or slow_window <= fast_window:
        raise ValueError("invalid MA windows")

    strategy = MovingAverageCrossover(fast_window=fast_window, slow_window=slow_window)
    return _run_backtest(
        prices=prices,
        strategy=strategy,
        initial_capital=float(parameters.get("_initial_capital", 10_000.0)),
        commission_rate=float(parameters.get("commission_rate", 0.001)),
        position_size_fraction=float(parameters.get("position_size_fraction", 1.0)),
        slippage_rate=float(parameters.get("slippage_rate", 0.0)),
    )


def _run_rsi(prices: list[float], parameters: dict[str, float]) -> StrategyRunOutput:
    period = int(parameters.get("period", 14))
    overbought = float(parameters.get("overbought", 70.0))
    oversold = float(parameters.get("oversold", 30.0))
    strategy = RSIStrategy(period=period, overbought=overbought, oversold=oversold)
    return _run_backtest(
        prices=prices,
        strategy=strategy,
        initial_capital=float(parameters.get("_initial_capital", 10_000.0)),
        commission_rate=float(parameters.get("commission_rate", 0.001)),
        position_size_fraction=float(parameters.get("position_size_fraction", 1.0)),
        slippage_rate=float(parameters.get("slippage_rate", 0.0)),
    )


def _run_macd(prices: list[float], parameters: dict[str, float]) -> StrategyRunOutput:
    fast_period = int(parameters.get("fast_period", 12))
    slow_period = int(parameters.get("slow_period", 26))
    signal_period = int(parameters.get("signal_period", 9))
    if fast_period >= slow_period:
        raise ValueError("fast_period must be < slow_period")
    strategy = MACDStrategy(
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
    )
    return _run_backtest(
        prices=prices,
        strategy=strategy,
        initial_capital=float(parameters.get("_initial_capital", 10_000.0)),
        commission_rate=float(parameters.get("commission_rate", 0.001)),
        position_size_fraction=float(parameters.get("position_size_fraction", 1.0)),
        slippage_rate=float(parameters.get("slippage_rate", 0.0)),
    )


STRATEGY_REGISTRY: dict[str, StrategyRunner] = {
    "ma_crossover_v1": _run_ma_crossover,
    "rsi_v1": _run_rsi,
    "macd_v1": _run_macd,
}


@dataclass
class TradingAdapter:
    initial_capital: float = 10_000.0
    commission_rate: float = 0.001
    train_ratio: float = 1.0
    position_size_fraction: float = 1.0
    slippage_rate: float = 0.0

    def _load_close_prices(self, dataset_id: str) -> list[float]:
        prices: list[float] = []
        with open(dataset_id, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                prices.append(float(row["close"]))
        if len(prices) < 20:
            raise ValueError("dataset needs at least 20 rows")
        return prices

    def _compute_metrics(
        self,
        *,
        runner: StrategyRunner,
        prices: list[float],
        strategy_parameters: dict[str, float],
    ) -> dict[str, float]:
        (
            final_equity,
            trade_count,
            equity_curve,
            trade_pnls,
            commission_paid,
            slippage_paid,
        ) = runner(prices, strategy_parameters)
        equity_returns = [
            (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            for i in range(1, len(equity_curve))
            if equity_curve[i - 1] != 0
        ]

        total_return = profitability_score(self.initial_capital, final_equity)
        return {
            "initial_equity": float(self.initial_capital),
            "final_equity": float(final_equity),
            "total_return": float(total_return),
            "trade_count": float(trade_count),
            "commission_paid": float(commission_paid),
            "slippage_paid": float(slippage_paid),
            "max_drawdown": float(max_drawdown(equity_curve)),
            "annualized_volatility": float(annualized_volatility(equity_returns)),
            "sharpe_ratio": float(sharpe_ratio(equity_returns)),
            "win_rate": float(win_rate(trade_pnls)),
        }

    def _run_on_price_list(
        self,
        prices: list[float],
        strategy_id: str,
        parameters: dict[str, float],
    ) -> dict[str, float]:
        runner = STRATEGY_REGISTRY.get(strategy_id)
        if runner is None:
            raise ValueError(f"unsupported strategy_id: {strategy_id}")

        strategy_parameters = {
            "_initial_capital": self.initial_capital,
            "commission_rate": self.commission_rate,
            "position_size_fraction": self.position_size_fraction,
            "slippage_rate": self.slippage_rate,
            **parameters,  # parameters can override commission_rate
        }
        return self._compute_metrics(
            runner=runner,
            prices=prices,
            strategy_parameters=strategy_parameters,
        )

    def _compute_score(self, metrics: dict[str, float]) -> float:
        scoring_weights = load_scoring_weights()
        return composite_score(
            metrics,
            {
                "return": scoring_weights["return_weight"],
                "sharpe": scoring_weights["sharpe_weight"],
                "drawdown": scoring_weights["drawdown_weight"],
            },
        )

    def run(
        self,
        *,
        dataset_id: str,
        strategy_id: str,
        parameters: dict[str, float],
        seed: int,
    ) -> DomainRunResult:
        if self.train_ratio <= 0 or self.train_ratio > 1.0:
            raise ValueError("train_ratio must be within (0, 1]")

        delay = float(parameters.get("_delay_seconds", 0.0))
        if delay > 0:
            time.sleep(delay)

        prices = self._load_close_prices(dataset_id)
        split_idx = max(1, int(len(prices) * self.train_ratio))
        train_prices = prices[:split_idx]
        test_prices = prices[split_idx:] if self.train_ratio < 1.0 else prices

        if self.train_ratio < 1.0:
            if len(train_prices) < 30:
                raise ValueError(
                    "train split must have at least 30 rows when train_ratio < 1.0"
                )
            if len(test_prices) < 10:
                raise ValueError(
                    "test split must have at least 10 rows when train_ratio < 1.0"
                )

        train_metrics = self._run_on_price_list(train_prices, strategy_id, parameters)
        test_metrics = self._run_on_price_list(test_prices, strategy_id, parameters)

        train_score = self._compute_score(train_metrics)
        test_score = self._compute_score(test_metrics)

        return DomainRunResult(
            metrics=test_metrics,
            score=train_score,
            artifacts={
                "train_score": train_score,  # type: ignore[dict-item]
                "test_score": test_score,  # type: ignore[dict-item]
            },
        )

    def run_on_prices(
        self,
        *,
        prices: list[float],
        strategy_id: str,
        parameters: dict[str, float],
        seed: int,
    ) -> DomainRunResult:
        if len(prices) < 20:
            raise ValueError("prices list needs at least 20 rows")

        delay = float(parameters.get("_delay_seconds", 0.0))
        if delay > 0:
            time.sleep(delay)

        metrics = self._run_on_price_list(prices, strategy_id, parameters)
        score = self._compute_score(metrics)
        return DomainRunResult(metrics=metrics, score=score, artifacts={})
