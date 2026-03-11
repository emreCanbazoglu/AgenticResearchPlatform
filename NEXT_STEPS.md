# Next Steps Before Implementation

Primary planning reference:

- `RESEARCH_PLATFORM_PLANNING.md`

Execution order:

1. Define canonical `ExperimentJob` schema and state machine.
2. Finalize optimizer plugin contract (genetic, Bayesian, bandit).
3. Specify scheduler policies (priority, fairness, quotas, retry).
4. Define domain adapter contracts for general-purpose research usage.
5. Add game economy objective and guardrail specification.
6. Write worker failure-mode runbook and determinism checklist.

Definition of ready (before coding):

- Interfaces are versioned and documented.
- Reproducibility invariants are explicitly testable.
- Batch lifecycle, retries, and idempotency behavior are unambiguous.
