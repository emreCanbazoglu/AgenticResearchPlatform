# Phase 8: Autonomous Self-Learning Cycle (Trading)

## Purpose

Deliver full self-learning iteration in trading domain while preserving deterministic execution and governance controls.

## Scope

- Persistent memory state for loop:
  - strategy history
  - parameter history
  - performance/failure memory
  - active population
- Loop controller implementing:
  - analyze -> propose -> implement -> review -> execute -> score -> memory update -> repeat
- Exploration/exploitation policy controls
- Termination criteria enforcement
- Safety policy:
  - no external APIs for strategy code
  - deterministic checks required before execution
  - approval and rollback rules for promoted strategies

## Deliverables

- `agents/memory.py`
- `agents/loop_controller.py`
- `agents/policies/exploration_exploitation.py`
- `agents/guards/safety.py`
- trading-domain loop runner entrypoint

## Acceptance Criteria

- Multi-iteration trading loop improves or maintains objective under configured policy.
- Loop survives interruption and resumes from last committed state.
- Every iteration logs required observability fields:
  - iteration id
  - candidate count
  - approved count
  - score distribution
  - selected strategies
  - rejected reasons
- Deterministic replay of same loop state reproduces decisions and results.

## Test Checklist

- Add `tests/deterministic/test_agentic_loop_replay.py`
- Add `tests/integration/test_agentic_loop_trading_end_to_end.py`
- Add `tests/integration/test_agentic_loop_resume.py`

## Exit Gate

Trading agentic loop is executable end-to-end with reproducible outputs and safety gates enabled.
