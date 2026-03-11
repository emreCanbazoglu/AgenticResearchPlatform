# Data Model: 001 Research Platform Orchestration

## Core Entities

- Campaign
- Batch
- ExperimentJob
- WorkerLease
- ExperimentResult
- OptimizerState
- LineageRecord
- AuditEvent

## Constraints

- `(job_id, attempt)` uniquely identifies an execution attempt.
- One terminal result per job attempt.
- Batch lifecycle transitions must follow the defined state machine.
- Campaign snapshot must reference immutable versions for datasets, policy, and scoring config.
