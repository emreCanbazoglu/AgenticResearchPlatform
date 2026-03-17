from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MACDStrategy:
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9

    def _sma(self, prices: list[float], idx: int, window: int) -> float:
        return sum(prices[idx - window + 1 : idx + 1]) / window

    def _macd_at(self, prices: list[float], idx: int) -> float:
        fast_ma = self._sma(prices, idx, self.fast_period)
        slow_ma = self._sma(prices, idx, self.slow_period)
        return fast_ma - slow_ma

    def signal(self, prices: list[float], idx: int) -> int:
        if idx < self.slow_period + self.signal_period:
            return 0

        macd_line = self._macd_at(prices, idx)
        recent_macd_values = [
            self._macd_at(prices, i) for i in range(idx - self.signal_period + 1, idx + 1)
        ]
        signal_line = sum(recent_macd_values) / self.signal_period

        if macd_line > signal_line:
            return 1
        if macd_line < signal_line:
            return -1
        return 0
