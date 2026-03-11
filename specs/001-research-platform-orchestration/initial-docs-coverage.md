# Initial Docs Coverage Matrix

This matrix maps initial project docs to implementation phases and status.

Legend:
- `DONE`: implemented
- `PLANNED`: explicitly phased with tasks
- `PARTIAL`: implemented baseline; fidelity expansion needed

## README.md

- Deterministic execution -> `DONE` (Phases 0-4)
- Reproducible experiments -> `DONE` (Phases 0-4)
- Automated experimentation over strategy space -> `DONE` baseline (Phases 1-3), `PLANNED` full agentic loop (Phases 7-8)
- Extensible to other domains -> `DONE` baseline (Phase 3), `PLANNED` richer domain packages (Phase 5+)

## ARCHITECTURE.md (8 layers)

1. Market Replay Layer -> `PARTIAL` (CSV replay exists; full replay-engine abstractions `PLANNED` in Phase 6)
2. Strategy Layer -> `PARTIAL` (MA strategy + adapters; full Strategy API lifecycle `PLANNED` in Phase 7)
3. Execution Simulator -> `PARTIAL` (basic execution; realistic costs/fills `PLANNED` in Phase 6)
4. Portfolio Simulator -> `PARTIAL` (equity/profitability only; richer portfolio state `PLANNED` in Phase 6)
5. Scoring Engine -> `PARTIAL` (profitability baseline; full raw+risk+composite metrics `PLANNED` in Phase 5)
6. Experiment Runner -> `DONE` baseline (Phases 1-2)
7. Meta Controller -> `DONE` baseline parameter evolution (Phases 1-3), `PLANNED` full loop governance (Phases 7-8)
8. Persistence Layer -> `DONE` baseline (Phases 0, 4)

## EXPERIMENT_PROTOCOL.md

- Required inputs captured -> `DONE` baseline
- Reproducibility requirements -> `DONE`
- Output artifacts (equity/trades/metadata) -> `PARTIAL` (equity+metadata done; trade-log richness `PLANNED` Phase 6)

## STRATEGY_API.md

- `initialize`, `on_candle`, `generate_orders`, `on_fill`, `finalize` lifecycle -> `PLANNED` Phase 7
- Determinism and no external APIs -> `DONE` baseline constraints + `PLANNED` enforcement automation in Phase 8

## SCORING_SPEC.md

- Raw metrics set -> `PARTIAL`
- Risk metrics set -> `PLANNED` Phase 5
- Composite score config weighting -> `PLANNED` Phase 5

## META_CONTROLLER_SPEC.md

- Selection/elimination/allocation/variation generation/batch coordination -> `PARTIAL` (selection/mutation baseline done)
- AI-generated variations optional -> `PLANNED` Phase 7

## AGENT_WORKFLOW.md

- Designer/Implementer/Reviewer roles -> `PLANNED` Phase 7
- Parallel role pipelines + failure handling -> `PLANNED` Phase 7

## AGENTIC_LOOP_SPEC.md

- Full autonomous loop with persistent memory -> `PLANNED` Phase 8
- Exploration/exploitation control -> `PLANNED` Phase 8
- Termination conditions + observability fields + crash recovery -> `PLANNED` Phase 8

## Current Conclusion

No initial-doc requirement is omitted now.
All previously missing agentic-loop requirements are explicitly phased in Phase 7 and Phase 8.
