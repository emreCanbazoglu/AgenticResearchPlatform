# Data Model: 001 Research Platform Orchestration

## Core Entities

- Campaign
  - `campaign_id`, `status`, `snapshot_fingerprint`
- Batch
  - `batch_id`, `campaign_id`, `iteration`, `status`
- ExperimentJob
  - `job_id`, `campaign_id`, `batch_id`, `candidate_id`, `parent_candidate_id`, `domain`, `dataset_id`, `strategy_id`, `parameters`, `seed`, `trace_id`, `priority`, `attempt`
- ExperimentResult
  - `job_id`, `campaign_id`, `batch_id`, `attempt`, `status`, `score`, `metrics`, `trace_id`, `error`
- DeadLetterRecord
  - `job_id`, `campaign_id`, `batch_id`, `attempts`, `reason`
- AuditEvent
  - `trace_id`, `event_type`, `campaign_id`, `batch_id`, `job_id`, `attempt`, `payload`
- LineageRecord
  - `job_id`, `campaign_id`, `batch_id`, `candidate_id`, `parent_candidate_id`
- Checkpoint
  - `campaign_id`, `iteration`, `optimizer_state`, `best_score`, `best_parameters`, `trace_id`

## Constraints

- `(job_id, attempt)` uniquely identifies one execution attempt.
- One terminal result row per attempt (`INSERT OR IGNORE` idempotency).
- `job_id` is unique in active scheduling and lineage tracking.
- Campaign and batch statuses must follow lifecycle transitions.
- All events for one campaign run should share a single `trace_id`.

## Integrity Invariants

- `queued_jobs == started_jobs == completed_jobs` for successful batches.
- Lineage record count equals scheduled job count.
- Resume starts at `(latest_checkpoint.iteration + 1)`.
- Snapshot fingerprint must be stable for identical campaign configuration.

## Persistence Layout (SQLite)

Tables:
- `campaigns`
- `batches`
- `jobs`
- `results`
- `dead_letters`
- `audit_events`
- `lineage_records`
- `checkpoints`

## Migration Policy

- Create tables if missing on repository init.
- Backfill required columns with additive `ALTER TABLE` when absent.
- No destructive migration in MVP.
