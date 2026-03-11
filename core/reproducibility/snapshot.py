from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from core.reproducibility.fingerprint import stable_hash


@dataclass(frozen=True)
class CampaignSnapshot:
    campaign_id: str
    domain: str
    optimizer: str
    dataset_id: str
    strategy_id: str
    iterations: int
    batch_size: int
    seed: int
    parameters_space: dict[str, Any]

    def fingerprint(self) -> str:
        return stable_hash(asdict(self))
