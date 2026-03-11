from __future__ import annotations


def profitability_score(initial_equity: float, final_equity: float) -> float:
    if initial_equity <= 0:
        raise ValueError("initial_equity must be > 0")
    return (final_equity - initial_equity) / initial_equity
