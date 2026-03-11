from __future__ import annotations

from collections import defaultdict


class CampaignQuotaTracker:
    def __init__(self, max_concurrent_per_campaign: int) -> None:
        self.max_concurrent_per_campaign = max_concurrent_per_campaign
        self._active_counts = defaultdict(int)

    def can_schedule(self, campaign_id: str) -> bool:
        return self._active_counts[campaign_id] < self.max_concurrent_per_campaign

    def mark_started(self, campaign_id: str) -> None:
        self._active_counts[campaign_id] += 1

    def mark_finished(self, campaign_id: str) -> None:
        self._active_counts[campaign_id] = max(0, self._active_counts[campaign_id] - 1)
