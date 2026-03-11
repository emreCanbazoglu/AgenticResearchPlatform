# Phase 3: Optimizers and Domain Abstraction

## Purpose

Make orchestration domain-agnostic and support multiple optimization methods.

## Scope

- Domain adapter contract and registry
- Trading adapter + game economy adapter
- Optimizer selection per campaign
- Cross-domain execution through same orchestrator path

## Deliverables

- `domains/base.py`
- `core/execution/adapters.py`
- `domains/trading/adapter.py`
- `domains/game_economy/{adapter,objectives}.py`
- `meta/optimizers/bandit.py` (allocation scaffold)

## Acceptance Criteria

- Trading and game economy campaigns run via same campaign runner.
- Unsupported domain fails with clear deterministic error.

## Test Checklist

- `tests/unit/test_domain_adapter_contract.py`
- `tests/integration/test_cross_domain_campaign.py`

## Exit Gate

Cross-domain test must pass with no trading-specific leakage.
