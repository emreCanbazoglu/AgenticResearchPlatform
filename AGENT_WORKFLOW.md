# Parallel Agent Workflow Specification

## Purpose

Define a structured multi-agent development process for generating, implementing, and validating strategy improvements in parallel.

Agents operate asynchronously but coordinate through shared artifacts.

---

## Agent Roles

Three primary roles:

1. Designer Agent
2. Implementer Agent
3. Reviewer Agent

Each role has strict responsibilities.

---

## 1. Designer Agent

### Objective

Propose new strategy concepts or modifications based on prior experiment results.

### Inputs

- Experiment database
- Performance metrics
- Failure cases
- Strategy registry
- Scoring outputs

### Responsibilities

- Identify promising directions
- Generate strategy specifications
- Propose parameter ranges
- Avoid duplication of prior experiments
- Produce deterministic, testable designs

### Outputs

Structured design document:
StrategyProposal:
id: string
base_strategy: string | null
hypothesis: string
parameters:
param_name: range or value
expected_behavior: description
risk_profile: description
notes: optional

Designs must not contain executable code.

---

## 2. Implementer Agent

### Objective

Translate proposals into executable strategy implementations.

### Inputs

- StrategyProposal
- Strategy API specification
- Existing strategy templates

### Responsibilities

- Generate deterministic code
- Conform to Strategy Interface
- Validate syntax and structure
- Ensure no external dependencies
- Assign version identifiers

### Outputs

Executable strategy module:
StrategyImplementation:
strategy_id: string
version: integer
code_path: file reference
parameters: concrete values
dependencies: none (V1)

---

## 3. Reviewer Agent

### Objective

Evaluate implementations before execution.

### Inputs

- StrategyImplementation
- Static analysis results
- Prior failure logs

### Responsibilities

- Verify interface compliance
- Detect unsafe or invalid logic
- Check for duplication
- Confirm determinism
- Approve or reject implementation

### Outputs

ReviewResult:
strategy_id: string
approved: true | false
issues: list
risk_flags: optional
Rejected implementations return to Designer for revision.

---

## Parallel Execution Model

Multiple Designer → Implementer → Reviewer pipelines may run concurrently.

Key rules:

- No shared mutable state
- Communication via experiment database
- Unique identifiers for all artifacts
- Idempotent operations

---

## Artifact Flow

Designer → Proposal  
Implementer → Code  
Reviewer → Approval  
Approved → Experiment Runner

---

## Failure Handling

If implementation repeatedly fails review:

- Mark proposal as invalid
- Record failure reason
- Prevent automatic re-generation

---

## Extensibility

Future roles may include:

- Data Agent (feature engineering)
- Risk Agent (constraint enforcement)
- Allocation Agent (capital distribution)
