# Phase 4: Reliability and Observability

## Purpose

Make execution auditable, traceable, and recoverable in production-like conditions.

## Scope

- Trace propagation campaign -> batch -> job
- Structured audit events for lifecycle and job transitions
- Lineage records for each scheduled candidate/job
- Checkpoint and resume behaviors under interruption

## Deliverables

- `observability/{logging,metrics,tracing}.py`
- `persistence/repositories.py` (`audit_events`, `lineage_records`, `checkpoints`)
- audit event emission in `campaign.py` and `dispatcher.py`

## Acceptance Criteria

- All events in a campaign share one trace id.
- Queued/started/completed job sets are consistent.
- Lineage record count matches scheduled jobs.

## Test Checklist

- `tests/integration/test_audit_events.py`
- `tests/integration/test_audit_lineage.py`
- `tests/integration/test_resume_recovery.py`

## Exit Gate

Audit and lineage integrity tests must pass.
