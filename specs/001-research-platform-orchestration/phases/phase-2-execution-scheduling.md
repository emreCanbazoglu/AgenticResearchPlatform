# Phase 2: Execution and Scheduling

## Purpose

Run jobs in parallel with deterministic behavior and robust failure semantics.

## Scope

- Priority queue scheduling
- Per-campaign quota checks
- Worker dispatch with retries and timeout-driven failure handling
- Dead-letter capture and per-attempt result idempotency
- Heartbeat event emission during running jobs

## Deliverables

- `core/execution/dispatcher.py`
- `core/execution/worker.py`
- `core/execution/lease.py`
- `core/scheduling/{policy,priority_queue,quotas}.py`

## Acceptance Criteria

- Retry policy executes up to `max_attempts`.
- Timeouts create deterministic failed attempts and eventual dead-letter.
- No duplicate inserts for same `(job_id, attempt)`.

## Test Checklist

- `tests/unit/test_scheduler_policy.py`
- `tests/integration/test_retry_deadletter.py`
- `tests/integration/test_trading_mvp.py`

## Exit Gate

Failure-path tests must pass before multi-domain expansion.
