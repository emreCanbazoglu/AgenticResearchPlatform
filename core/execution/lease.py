from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class WorkerLease:
    job_id: str
    worker_id: str
    expires_at: datetime

    @classmethod
    def create(cls, job_id: str, worker_id: str, ttl_seconds: int = 30) -> "WorkerLease":
        return cls(
            job_id=job_id,
            worker_id=worker_id,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )

    def expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at
