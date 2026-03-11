from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CampaignRecord:
    campaign_id: str
    status: str
    snapshot_fingerprint: str


@dataclass(frozen=True)
class BatchRecord:
    batch_id: str
    campaign_id: str
    iteration: int
    status: str


@dataclass(frozen=True)
class ExperimentJob:
    job_id: str
    campaign_id: str
    batch_id: str
    candidate_id: str
    parent_candidate_id: str | None
    domain: str
    dataset_id: str
    strategy_id: str
    parameters: dict[str, Any]
    seed: int
    trace_id: str = ""
    priority: str = "standard"
    attempt: int = 1


@dataclass(frozen=True)
class ExperimentResult:
    job_id: str
    campaign_id: str
    batch_id: str
    attempt: int
    status: str
    score: float
    metrics: dict[str, Any]
    trace_id: str = ""
    error: str | None = None


@dataclass(frozen=True)
class DeadLetterRecord:
    job_id: str
    campaign_id: str
    batch_id: str
    attempts: int
    reason: str


@dataclass(frozen=True)
class AuditEvent:
    trace_id: str
    event_type: str
    campaign_id: str
    batch_id: str | None = None
    job_id: str | None = None
    attempt: int | None = None
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class LineageRecord:
    job_id: str
    campaign_id: str
    batch_id: str
    candidate_id: str
    parent_candidate_id: str | None = None
