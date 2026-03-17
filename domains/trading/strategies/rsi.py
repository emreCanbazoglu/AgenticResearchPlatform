from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RSIStrategy:
    period: int = 14
    overbought: float = 70.0
    oversold: float = 30.0

    def signal(self, prices: list[float], idx: int) -> int:
        if idx < self.period:
            return 0

        gains: list[float] = []
        losses: list[float] = []
        for i in range(idx - self.period + 1, idx + 1):
            delta = prices[i] - prices[i - 1]
            gains.append(max(delta, 0.0))
            losses.append(max(-delta, 0.0))

        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period

        if avg_loss == 0.0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        if rsi < self.oversold:
            return 1
        if rsi > self.overbought:
            return -1
        return 0
