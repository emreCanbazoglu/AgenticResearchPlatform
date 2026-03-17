from __future__ import annotations

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


class LongshotFadeStrategy(BettingStrategy):
    def evaluate(self, snapshot: MarketSnapshot, parameters: dict[str, Any]) -> BetDecision:
        merged = {**self.default_parameters, **parameters}
        threshold_low = int(merged["threshold_low"])
        threshold_high = int(merged["threshold_high"])
        min_confidence = int(merged["min_confidence"])

        price_pct = snapshot.current_price * 100.0

        if price_pct < threshold_low:
            estimated_prob = (price_pct * 0.6) / 100.0
            confidence = _clamp01((threshold_low - price_pct) / threshold_low)
            if confidence * 100.0 >= min_confidence:
                return BetDecision(
                    action=BetAction.BET_NO,
                    estimated_probability=_blend_llm(estimated_prob, merged),
                    confidence=confidence,
                )

        elif price_pct > threshold_high:
            estimated_prob = (price_pct * 1.1) / 100.0
            confidence = _clamp01((price_pct - threshold_high) / (100 - threshold_high))
            if confidence * 100.0 >= min_confidence:
                return BetDecision(
                    action=BetAction.BET_YES,
                    estimated_probability=_blend_llm(estimated_prob, merged),
                    confidence=confidence,
                )

        return BetDecision(
            action=BetAction.PASS,
            estimated_probability=_clamp01(snapshot.current_price),
            confidence=0.0,
        )

    @property
    def default_parameters(self) -> dict[str, Any]:
        return {
            "threshold_low": 15,
            "threshold_high": 85,
            "min_confidence": 30,
            "llm_weight": 30,
        }

    @property
    def search_space(self) -> dict[str, tuple[int, int]]:
        return {
            "threshold_low": (5, 25),
            "threshold_high": (75, 95),
            "min_confidence": (10, 50),
            "llm_weight": (0, 100),
        }
