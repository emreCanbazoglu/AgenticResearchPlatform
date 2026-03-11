# Phase 7: Agent Runtime Loop (Designer/Implementer/Reviewer)

## Purpose

Implement the role-based autonomous loop defined in `AGENT_WORKFLOW.md` and `AGENTIC_LOOP_SPEC.md`.

## Scope

- Runtime role services:
  - `DesignerAgent` (proposal generation)
  - `ImplementerAgent` (deterministic implementation generation)
  - `ReviewerAgent` (compliance/safety approval)
- Persistent artifacts:
  - `StrategyProposal`
  - `StrategyImplementation`
  - `ReviewResult`
- Parallel role pipelines with idempotent operations
- Approval-gated routing into experiment execution

## Deliverables

- `agents/designer.py`
- `agents/implementer.py`
- `agents/reviewer.py`
- `agents/pipeline.py`
- persistence tables/repos for proposals/implementations/reviews

## Acceptance Criteria

- Pipeline supports `Designer -> Implementer -> Reviewer -> Runner` flow.
- Rejected implementations never enter experiment execution.
- Repeated failures are recorded and proposal is marked invalid.
- Parallel pipelines produce unique artifact IDs with no shared mutable in-memory state.

## Test Checklist

- Add `tests/integration/test_agent_pipeline_happy_path.py`
- Add `tests/integration/test_agent_pipeline_rejection_path.py`
- Add `tests/integration/test_agent_pipeline_parallel_idempotency.py`

## Exit Gate

Agent pipeline tests must pass and produce auditable artifacts.
