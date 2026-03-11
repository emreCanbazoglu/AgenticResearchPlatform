from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MovingAverageCrossover:
    fast_window: int
    slow_window: int

    def signal(self, prices: list[float], idx: int) -> int:
        if idx < self.slow_window:
            return 0
        fast = sum(prices[idx - self.fast_window + 1 : idx + 1]) / self.fast_window
        slow = sum(prices[idx - self.slow_window + 1 : idx + 1]) / self.slow_window
        if fast > slow:
            return 1
        if fast < slow:
            return -1
        return 0
