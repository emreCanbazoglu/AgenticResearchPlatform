from __future__ import annotations

from core.scheduling.priority_queue import JobPriorityQueue
from persistence.models import ExperimentJob


def test_priority_queue_orders_interactive_first() -> None:
    queue = JobPriorityQueue()
    queue.push(
        ExperimentJob(
            job_id="j-standard",
            campaign_id="c1",
            batch_id="b1",
            candidate_id="cand-1",
            parent_candidate_id=None,
            domain="trading",
            dataset_id="d",
            strategy_id="s",
            parameters={},
            seed=1,
            priority="standard",
        )
    )
    queue.push(
        ExperimentJob(
            job_id="j-interactive",
            campaign_id="c1",
            batch_id="b1",
            candidate_id="cand-2",
            parent_candidate_id=None,
            domain="trading",
            dataset_id="d",
            strategy_id="s",
            parameters={},
            seed=1,
            priority="interactive",
        )
    )

    assert queue.pop().job_id == "j-interactive"
    assert queue.pop().job_id == "j-standard"
