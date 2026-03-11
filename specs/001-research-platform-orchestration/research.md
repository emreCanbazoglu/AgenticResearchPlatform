# Research Notes: 001 Research Platform Orchestration

## Objective

Capture technical decisions, open questions, and validation criteria for implementing deterministic multi-domain research orchestration.

## Initial Decisions

- Keep deterministic execution as the primary invariant.
- Implement optimizer plugins behind a strict base contract.
- Start with local multiprocessing and queue abstraction; add distributed backend next.
- Keep persistence schema Postgres-ready while preserving local SQLite mode.
- Introduce domain adapters before game economy-specific logic.

## Open Questions

- Queue backend selection for first distributed iteration.
- Exact metric/tracing stack for observability.
- Scoring scalarization defaults for multi-objective domains.
