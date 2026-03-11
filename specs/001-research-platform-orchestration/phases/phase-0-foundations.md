# Phase 0: Foundations

## Purpose

Establish deterministic contracts and persistence primitives required by all later phases.

## Scope

- Canonical models (`Campaign`, `Batch`, `ExperimentJob`, `ExperimentResult`, `AuditEvent`, `LineageRecord`)
- Deterministic fingerprinting and campaign snapshot
- Lifecycle state enums and transition guards
- SQLite schema initialization with safe backfill for new columns

## Deliverables

- `core/reproducibility/fingerprint.py`
- `core/reproducibility/snapshot.py`
- `core/orchestration/state_machine.py`
- `persistence/models.py`
- `persistence/repositories.py`

## Acceptance Criteria

- Same snapshot input yields same fingerprint.
- Invalid status transition raises deterministic error.
- Existing DB files upgrade without destructive migration.

## Test Checklist

- `tests/deterministic/test_campaign_replay.py`
- `tests/integration/test_lifecycle_persistence.py`

## Exit Gate

Do not proceed unless deterministic replay and lifecycle persistence pass.
