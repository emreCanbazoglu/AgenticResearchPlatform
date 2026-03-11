# Agentic Loop Specification

## Purpose

Define a fully autonomous iteration cycle for strategy discovery and evaluation.

The loop continuously proposes, tests, and refines strategies.

---

## High-Level Loop

1. Analyze past results
2. Generate new candidates
3. Validate implementations
4. Run experiments
5. Score performance
6. Update memory
7. Repeat

---

## Formal Loop Definition

while system_active:

proposals = Designer.generate(memory)

implementations = Implementer.build(proposals)

approved = Reviewer.validate(implementations)

results = ExperimentRunner.execute(approved)

scores = ScoringEngine.evaluate(results)

memory.update(scores)

## MetaController.adjust_population(memory)

## Loop Components

### 1. Memory State

Central knowledge base containing:

- Strategy history
- Parameters tested
- Performance metrics
- Failure cases
- Active strategy pool

Memory must be persistent.

---

### 2. Candidate Generation

New strategies may be produced via:

- Parameter mutation
- Parameter recombination
- Structural modification
- AI-assisted design
- Random exploration (optional)

---

### 3. Validation Gate

All candidates must pass:

- Interface compliance
- Determinism checks
- Safety constraints
- Redundancy checks

---

### 4. Experiment Execution

Each approved strategy is tested using identical conditions:

- Same dataset
- Same capital
- Same cost model
- Same simulation period

Ensures fair comparison.

---

### 5. Scoring

Each run produces:

- Raw metrics
- Risk metrics
- Composite score

Scores determine survival.

---

### 6. Population Update

Meta Controller applies selection:

- Keep top performers
- Remove weak strategies
- Maintain diversity
- Allocate simulation budget

---

## Exploration vs Exploitation

System must balance:

Exploration:

- Novel strategies
- High variance
- Unknown behavior

Exploitation:

- Refinement of strong performers
- Parameter tuning

Exact policy configurable.

---

## Termination Conditions (Optional)

Loop may stop if:

- No improvement over N iterations
- Budget exhausted
- Manual intervention
- Performance threshold reached

---

## Determinism Requirements

Given identical inputs:

- Replay results must be identical
- Scores must be identical
- Decisions must be reproducible

Randomness must be seeded.

---

## Safety Constraints

V1 restrictions:

- No external network calls
- No real trading actions
- No file system modification outside sandbox
- No self-modifying core engine code

---

## Observability

Each iteration must log:

- Iteration ID
- Candidate count
- Approved count
- Scores distribution
- Selected strategies
- Rejected reasons

---

## Failure Recovery

If loop crashes:

- Resume from last committed state
- No loss of experiment history
