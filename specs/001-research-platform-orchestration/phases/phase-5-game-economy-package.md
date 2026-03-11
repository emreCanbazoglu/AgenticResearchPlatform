# Phase 5: Game Economy Package

## Purpose

Productize non-trading usage with explicit objective bundle and guardrails.

## Scope

- Extend game economy objective bundle beyond placeholder score
- Add guardrails: inflation stability, sink/source bounds, fairness proxies
- Add scenario dataset fixtures and campaign examples

## Deliverables

- Expand `domains/game_economy/objectives.py`
- Add game-economy fixture data under `data/game_economy/`
- Add integration tests for guardrail pass/fail decisions

## Acceptance Criteria

- Campaign outputs objective + guardrail verdicts.
- Bad economy configurations are explicitly flagged.

## Test Checklist

- Add `tests/integration/test_game_economy_guardrails.py`
- Keep cross-domain tests passing.

## Exit Gate

Game economy optimization decisions are explainable and reproducible.
