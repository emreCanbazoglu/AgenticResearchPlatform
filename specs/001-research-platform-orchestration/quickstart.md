# Quickstart: 001 Research Platform Orchestration

## Prerequisites

- `uv` installed
- Run commands from repository root

## 1) Run tests

```bash
uv run --with pytest pytest
```

Expected: all tests pass.

## 2) Run trading MVP campaign

```bash
uv run python run_mvp.py
```

Expected output includes:
- Snapshot fingerprint
- Best profitability score
- Best parameters
- Per-batch summary

## 3) Verify deterministic replay manually

Run the same campaign command twice and confirm key outputs (snapshot hash and best result) match.

## 4) Resume example

Use campaign config with `stop_after_iteration=0`, then rerun with `resume_from_latest=True`.

Reference test:
- `tests/integration/test_resume_recovery.py`

## 5) Cross-domain run reference

Reference test:
- `tests/integration/test_cross_domain_campaign.py`

This validates that trading and game economy execute via the same orchestration engine.
