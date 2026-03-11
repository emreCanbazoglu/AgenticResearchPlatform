# Contract: Optimizer API

## Required Methods

- `suggest(batch_context) -> CandidateSet`
- `observe(batch_results) -> OptimizerStateDelta`
- `checkpoint() -> bytes`
- `restore(bytes) -> OptimizerState`

## Invariants

- Deterministic outputs for identical inputs and state.
- State transitions are versioned and serializable.
