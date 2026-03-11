# Research Notes: 001 Research Platform Orchestration

## Objective

Capture technical decisions, rationale, and open items for building a deterministic multi-domain experiment platform.

## Current Decisions (Implemented)

- Deterministic-first execution with explicit seeds and stable hashing.
- Optimizer plugin architecture (`genetic`, `bayesian`, `bandit` scaffold).
- Parallel execution via process pool with priority queue and quota checks.
- Retry and timeout handling with dead-letter persistence.
- Checkpoint and resume support at campaign iteration boundaries.
- Domain abstraction with adapter registry (`trading`, `game_economy`).
- Audit event stream and lineage records for traceability.
- SQLite local mode with compatibility-safe schema backfill.

## Tradeoffs

- SQLite chosen for local velocity; not final production metadata store.
- Timeout-based lease proxy used for MVP; full distributed lease ownership still pending.
- Bayesian optimizer currently deterministic skeleton, not full TPE/GP stack.
- Game economy objective model is minimal; guardrails need richer economics logic.

## Versions and Runtime

- Python: `>=3.11` (tested with `3.13` via `uv run`)
- Test runner: `pytest`
- Local environment manager: `uv`

## Validation Snapshot

- Automated tests: `14 passed`
- MVP campaign run: deterministic and positive trading profitability score.

## Open Questions

- Which distributed queue backend first (Redis, RabbitMQ, cloud queue)?
- Which production observability sink and retention strategy?
- Final multi-objective scalarization policy for non-trading domains?
