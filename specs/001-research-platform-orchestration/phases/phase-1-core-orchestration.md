# Phase 1: Core Orchestration

## Purpose

Implement campaign iteration loop and batch/job planning with optimizer integration.

## Scope

- Campaign config and runtime aggregate
- Batch planning from candidates
- Optimizer suggest/observe/checkpoint/restore hooks
- Per-batch checkpoint persistence and resume entry point

## Deliverables

- `core/orchestration/campaign.py`
- `core/orchestration/batch.py`
- `core/orchestration/resume.py`
- `core/execution/planner.py`
- `meta/optimizers/{base,genetic,bayesian,factory}.py`

## Acceptance Criteria

- Campaign can run multi-iteration deterministically.
- Campaign can stop early and resume from last checkpoint.
- Best score/params persist across resumed execution.

## Test Checklist

- `tests/deterministic/test_campaign_replay.py`
- `tests/integration/test_resume_recovery.py`
- `tests/unit/test_optimizer_contract.py`

## Exit Gate

Resume test must pass before moving to scheduler/distributed concerns.
