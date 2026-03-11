from __future__ import annotations

PRIORITY_ORDER = {
    "interactive": 0,
    "standard": 1,
    "backfill": 2,
}


def priority_rank(priority: str) -> int:
    return PRIORITY_ORDER.get(priority, PRIORITY_ORDER["standard"])
