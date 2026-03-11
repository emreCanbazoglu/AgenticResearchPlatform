from __future__ import annotations

import csv
import time
from dataclasses import dataclass

from domains.base import DomainRunResult
from domains.trading.strategies.moving_average import MovingAverageCrossover
from scoring.metrics import profitability_score


@dataclass
class TradingAdapter:
    initial_capital: float = 10_000.0

    def _load_close_prices(self, dataset_id: str) -> list[float]:
        prices: list[float] = []
        with open(dataset_id, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                prices.append(float(row["close"]))
        if len(prices) < 20:
            raise ValueError("dataset needs at least 20 rows")
        return prices

    def run(
        self,
        *,
        dataset_id: str,
        strategy_id: str,
        parameters: dict[str, float],
        seed: int,
    ) -> DomainRunResult:
        if strategy_id != "ma_crossover_v1":
            raise ValueError(f"unsupported strategy_id: {strategy_id}")
        delay = float(parameters.get("_delay_seconds", 0.0))
        if delay > 0:
            time.sleep(delay)
        prices = self._load_close_prices(dataset_id)

        fast_window = int(parameters["fast_window"])
        slow_window = int(parameters["slow_window"])
        if fast_window < 2 or slow_window <= fast_window:
            raise ValueError("invalid MA windows")

        strategy = MovingAverageCrossover(fast_window=fast_window, slow_window=slow_window)

        cash = self.initial_capital
        position = 0.0
        trade_count = 0

        for i in range(len(prices)):
            signal = strategy.signal(prices, i)
            price = prices[i]

            # Fully-invested long-only for deterministic MVP.
            if signal > 0 and position == 0.0:
                position = cash / price
                cash = 0.0
                trade_count += 1
            elif signal < 0 and position > 0.0:
                cash = position * price
                position = 0.0
                trade_count += 1

        final_equity = cash + position * prices[-1]
        total_return = profitability_score(self.initial_capital, final_equity)

        metrics = {
            "initial_equity": self.initial_capital,
            "final_equity": final_equity,
            "total_return": total_return,
            "trade_count": float(trade_count),
        }
        return DomainRunResult(metrics=metrics, score=total_return, artifacts={})
