from __future__ import annotations

from enum import Enum


class CampaignStatus(str, Enum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BatchStatus(str, Enum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


VALID_TRANSITIONS = {
    CampaignStatus.DRAFT: {CampaignStatus.QUEUED, CampaignStatus.CANCELLED},
    CampaignStatus.QUEUED: {CampaignStatus.RUNNING, CampaignStatus.CANCELLED},
    CampaignStatus.RUNNING: {
        CampaignStatus.PARTIAL,
        CampaignStatus.COMPLETED,
        CampaignStatus.FAILED,
        CampaignStatus.CANCELLED,
    },
    CampaignStatus.PARTIAL: {CampaignStatus.RUNNING, CampaignStatus.COMPLETED, CampaignStatus.FAILED},
    CampaignStatus.COMPLETED: set(),
    CampaignStatus.FAILED: set(),
    CampaignStatus.CANCELLED: set(),
}


def assert_valid_transition(current: CampaignStatus, nxt: CampaignStatus) -> None:
    if nxt not in VALID_TRANSITIONS[current]:
        raise ValueError(f"Invalid transition: {current} -> {nxt}")
