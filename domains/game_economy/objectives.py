from __future__ import annotations


def evaluate_guardrails(metrics: dict[str, float]) -> dict[str, bool]:
    return {
        "no_runaway_inflation": abs(metrics.get("economy_balance", 0.0)) < 0.2,
    }
