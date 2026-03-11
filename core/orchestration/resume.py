from __future__ import annotations

from persistence.repositories import SqliteExperimentRepository


def resume_from_checkpoint(db_path: str, campaign_id: str) -> dict | None:
    repo = SqliteExperimentRepository(db_path)
    checkpoint = repo.get_latest_checkpoint(campaign_id)
    if checkpoint is None:
        return None
    return dict(checkpoint)
