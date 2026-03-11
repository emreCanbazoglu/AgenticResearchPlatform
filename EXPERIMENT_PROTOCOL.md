# Experiment Protocol

Defines how experiments are executed and recorded.

## Required Inputs

- Dataset identifier
- Strategy configuration
- Parameter set
- Initial capital
- Simulation period

---

## Execution Steps

1. Load dataset
2. Initialize replay engine
3. Instantiate strategy
4. Run simulation loop
5. Compute metrics
6. Compute composite score
7. Persist results

---

## Reproducibility Requirements

Each experiment must store:

- Dataset version
- Strategy version
- Parameter values
- System configuration
- Random seed (if used)

---

## Output Artifacts

- Metrics summary
- Equity curve
- Trade log
- Composite score
- Execution metadata
