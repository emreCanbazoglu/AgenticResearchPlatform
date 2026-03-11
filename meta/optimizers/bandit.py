from __future__ import annotations

from collections import defaultdict


class BanditAllocator:
    """Simple UCB-style score tracker for future scheduler integration."""

    def __init__(self) -> None:
        self.counts = defaultdict(int)
        self.rewards = defaultdict(float)

    def observe(self, arm: str, reward: float) -> None:
        self.counts[arm] += 1
        self.rewards[arm] += reward

    def average_reward(self, arm: str) -> float:
        if self.counts[arm] == 0:
            return 0.0
        return self.rewards[arm] / self.counts[arm]
