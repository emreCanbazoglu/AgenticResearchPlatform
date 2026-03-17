from __future__ import annotations

from statistics import mean
from typing import Any

from domains.polymarket.base import BetAction, BetDecision, BettingStrategy, MarketSnapshot


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _blend_llm(own_estimate: float, merged: dict[str, Any]) -> float:
    llm_prior = merged.get("llm_prior")
    if llm_prior is None:
        return _clamp01(own_estimate)
    llm_weight = _clamp01(float(merged.get("llm_weight", 30)) / 100.0)
    return _clamp01((llm_weight * _clamp01(float(llm_prior))) + ((1.0 - llm_weight) * _clamp01(own_estimate)))


class MeanReversionStrategy(BettingStrategy):
    def evaluate(self, snapshot: MarketSnapshot, parameters: dict[str, Any]) -> BetDecision:
        merged = {**self.default_parameters, **parameters}
        mean_window = int(merged["mean_window"])
        deviation_threshold = int(merged["deviation_threshold"])
        reversion_strength = int(merged["reversion_strength"])

        if len(snapshot.price_history) < mean_window:
            return BetDecision(BetAction.PASS, _clamp01(snapshot.current_price), 0.0)

        baseline_mean = mean(snapshot.price_history[-mean_window:])
        deviation = (snapshot.current_price - baseline_mean) * 100.0

        if abs(deviation) < deviation_threshold:
            return BetDecision(BetAction.PASS, _clamp01(snapshot.current_price), 0.0)

        reversion_fraction = reversion_strength / 100.0
        estimated_prob = baseline_mean + (snapshot.current_price - baseline_mean) * (1 - reversion_fraction)
        confidence = _clamp01(abs(deviation) / 40.0)

        if deviation > 0:
            return BetDecision(BetAction.BET_NO, _blend_llm(estimated_prob, merged), confidence)

        return BetDecision(BetAction.BET_YES, _blend_llm(estimated_prob, merged), confidence)

    @property
    def default_parameters(self) -> dict[str, Any]:
        return {
            "mean_window": 54,
            "deviation_threshold": 15,
            "reversion_strength": 50,
            "llm_weight": 30,
        }

    @property
    def search_space(self) -> dict[str, tuple[int, int]]:
        return {
            "mean_window": (12, 96),
            "deviation_threshold": (5, 25),
            "reversion_strength": (20, 80),
            "llm_weight": (0, 100),
        }
