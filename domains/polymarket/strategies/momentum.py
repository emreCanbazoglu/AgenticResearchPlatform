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


class MomentumStrategy(BettingStrategy):
    def evaluate(self, snapshot: MarketSnapshot, parameters: dict[str, Any]) -> BetDecision:
        merged = {**self.default_parameters, **parameters}
        lookback_window = int(merged["lookback_window"])
        momentum_threshold = int(merged["momentum_threshold"])
        max_price = int(merged["max_price"])
        min_price = int(merged["min_price"])

        if len(snapshot.price_history) < lookback_window:
            return BetDecision(BetAction.PASS, _clamp01(snapshot.current_price), 0.0)

        recent = snapshot.price_history[-lookback_window:]
        move = (recent[-1] - recent[0]) * 100.0

        if abs(move) < momentum_threshold:
            return BetDecision(BetAction.PASS, _clamp01(snapshot.current_price), 0.0)

        if not (min_price <= snapshot.current_price * 100.0 <= max_price):
            return BetDecision(BetAction.PASS, _clamp01(snapshot.current_price), 0.0)

        confidence = _clamp01(abs(move) / 30.0)
        if move > 0:
            return BetDecision(
                action=BetAction.BET_YES,
                estimated_probability=_blend_llm(snapshot.current_price + 0.05, merged),
                confidence=confidence,
            )

        return BetDecision(
            action=BetAction.BET_NO,
            estimated_probability=_blend_llm(snapshot.current_price - 0.05, merged),
            confidence=confidence,
        )

    @property
    def default_parameters(self) -> dict[str, Any]:
        return {
            "lookback_window": 13,
            "momentum_threshold": 8,
            "max_price": 75,
            "min_price": 25,
            "llm_weight": 30,
        }

    @property
    def search_space(self) -> dict[str, tuple[int, int]]:
        return {
            "lookback_window": (3, 24),
            "momentum_threshold": (2, 15),
            "max_price": (60, 90),
            "min_price": (10, 40),
            "llm_weight": (0, 100),
        }
