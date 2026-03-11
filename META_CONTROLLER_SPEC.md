# Meta Controller Specification

## Purpose

Automates strategy selection and evolution across experiment batches.

---

## Core Responsibilities

### Selection

Choose top-performing strategies based on composite score.

---

### Elimination

Discard strategies below performance threshold.

---

### Capital Allocation (Simulated)

Assign capital weights to selected strategies.

No real capital involved.

---

### Variation Generation

Create new candidate strategies via:

- Parameter mutation
- Parameter crossover (optional)
- AI-generated variations (optional)

---

### Batch Coordination

Schedule and run multiple experiments.

---

## V1 Constraints

- No reinforcement learning required
- No neural networks required
- Heuristic or rule-based logic is acceptable
