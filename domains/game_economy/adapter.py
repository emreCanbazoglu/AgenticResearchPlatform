from __future__ import annotations

from dataclasses import dataclass

from domains.base import DomainRunResult


@dataclass
class GameEconomyAdapter:
    def run(
        self,
        *,
        dataset_id: str,
        strategy_id: str,
        parameters: dict[str, float],
        seed: int,
    ) -> DomainRunResult:
        # Placeholder adapter to validate domain-agnostic orchestration wiring.
        balance = parameters.get("reward_multiplier", 1.0) - parameters.get("sink_multiplier", 1.0)
        score = -abs(balance)
        metrics = {
            "economy_balance": balance,
            "score_proxy": score,
        }
        return DomainRunResult(metrics=metrics, score=score, artifacts={})
