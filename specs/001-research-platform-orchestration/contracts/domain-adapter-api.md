# Contract: Domain Adapter API

## Required Interfaces

- `EnvironmentAdapter`
- `PolicyAdapter`
- `Evaluator`
- `ConstraintSet`

## Invariants

- Orchestrator remains domain-agnostic.
- Adapter outputs support reproducible experiment execution.
