# Spec 003 — Optimizer Quality

## Goal

Replace the two optimizer stubs with real sample-efficient algorithms so that the platform can meaningfully improve strategy parameters across iterations.

## Scope

- Bayesian (TPE) optimizer — seeded, integer-space, learns from observations
- Bandit (UCB1) optimizer — fixed candidate pool, UCB exploration/exploitation, proper `Optimizer` subclass

## Tasks

| # | Task | Depends on | Status |
|---|---|---|---|
| 01 | Bayesian TPE optimizer | — | Pending |
| 02 | Bandit UCB1 optimizer | — | Pending |

Tasks 01 and 02 are independent and can be dispatched in parallel.

## Definition of Done

- [ ] Both tasks complete
- [ ] `uv run pytest` passes with no failures
- [ ] `BayesianOptimizer.suggest()` returns different parameter sets across iterations (not the same defaults every time)
- [ ] `BanditAllocator` is replaced by a proper `Optimizer` subclass registered as `"bandit"` in `factory.py`
- [ ] Both optimizers are deterministic given the same seed
