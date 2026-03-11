# Phase 6: Production Hardening

## Purpose

Prepare for multi-machine orchestration and operational safety.

## Scope

- Queue backend abstraction for distributed workers
- Worker lease ownership persistence and heartbeat reconciliation
- Operational runbooks and failure mode playbooks
- Optional API/CLI entrypoints for campaign execution and inspection

## Deliverables

- Queue backend interface and at least one remote adapter
- Worker lease table and reconciliation loop
- Runbooks under `docs/runbooks/`
- CLI wrapper (optional) for campaign start/status/reproduce

## Acceptance Criteria

- Horizontal workers can execute without duplicate terminal results.
- Recovery from worker loss is automatic and auditable.

## Test Checklist

- Distributed simulation test (mocked backend acceptable initially)
- Backpressure/queue-depth policy tests

## Exit Gate

Reliability SLO and reproducibility checks documented and pass in CI.
