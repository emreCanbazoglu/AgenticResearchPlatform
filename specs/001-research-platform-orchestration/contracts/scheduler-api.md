# Contract: Scheduler API

## Responsibilities

- Priority-aware job ordering
- Fair-share enforcement
- Quota evaluation
- Retry/dead-letter routing

## Invariants

- No duplicate terminal state writes.
- Policy decisions are explainable and auditable.
