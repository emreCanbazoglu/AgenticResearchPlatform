# Session Handoff: 001 Research Platform Orchestration

## Current Implementation Status

- Core deterministic orchestration: complete
- Parallel execution + scheduler policy: complete
- Retry/timeout/dead-letter: complete
- Checkpoint and resume: complete
- Domain abstraction (trading + game economy): complete
- Audit/trace/lineage persistence: complete
- Remaining work: docs closure tasks + full agent runtime loop + autonomous self-learning loop

## Task Status

From `tasks.md`:
- Completed: `40`
- Remaining: `19` (`T041`-`T059`)

## Next Immediate Actions

1. Finalize contracts and research docs (`T041`-`T043`).
2. Expand quickstart with domain-specific run examples (`T044`).
3. Re-run full suite and log deterministic proof in research (`T045`).
4. Start Phase 8 agent runtime loop (`T046`-`T054`).
5. Implement full autonomous loop for trading (`T055`-`T059`).

## Core Commands

```bash
uv run --with pytest pytest
uv run python run_mvp.py
```

## Key Entry Points

- Campaign runner: `core/orchestration/campaign.py`
- Dispatcher: `core/execution/dispatcher.py`
- Persistence: `persistence/repositories.py`
- Trading adapter: `domains/trading/adapter.py`
- Feature task board: `specs/001-research-platform-orchestration/tasks.md`
