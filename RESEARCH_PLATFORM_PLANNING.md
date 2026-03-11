# Agentic Research Platform Planning Blueprint

## Why this plan

Current docs define a deterministic, replay-first trading research system. This plan extends that baseline into an implementation-ready architecture for:

- Strategy evolution methods (genetic, Bayesian, bandit)
- Parallel and distributed experiment execution
- Batch compute scheduling
- Domain generalization beyond trading
- Game economy optimization reuse
- Production-grade orchestration patterns

This is a planning document only. No runtime behavior is introduced here.

---

## Target architecture evolution

Keep the existing 8 layers and introduce three cross-cutting planes:

1. Search Plane
- Owns candidate generation and adaptive selection logic
- Hosts genetic, Bayesian, and bandit engines

2. Compute Plane
- Owns job queueing, worker leasing, retries, and capacity policy
- Runs experiments in parallel across local and distributed workers

3. Platform Plane
- Owns domain abstraction, lineage, experiment registry, and governance
- Enables non-trading simulators with the same orchestration core

---

## 1) Strategy Evolution Methods

## 1.1 Unified optimizer interface

Define a single optimizer contract under `meta/optimizers/`:

- `suggest(batch_context) -> CandidateSet`
- `observe(batch_results) -> OptimizerStateDelta`
- `checkpoint() -> bytes`
- `restore(bytes) -> OptimizerState`

`batch_context` includes:
- Search space schema
- Prior experiment history slice
- Compute budget (max trials, max wall-clock)
- Constraints (risk caps, min trade count, etc.)

All optimizers write deterministic state transitions for reproducibility.

## 1.2 Genetic search (global exploration)

Use for broad non-convex search across mixed parameter spaces.

Plan:
- Genome: typed parameter vector from strategy schema
- Selection: top-k tournament with diversity penalty
- Variation:
- Mutation rate by parameter type (categorical flip, bounded numeric perturbation)
- Crossover optional for V1 of this optimizer
- Elitism: carry forward top N unchanged
- Safety constraints: reject invalid genomes before scheduling

Recommended first use:
- Early-stage discovery or unknown strategy landscapes

## 1.3 Bayesian optimization (sample efficiency)

Use for expensive experiments when trial budget is limited.

Plan:
- Surrogate: TPE or Gaussian Process (choose TPE first for mixed spaces)
- Acquisition: expected improvement with constraint penalty
- Warm-start from prior completed runs
- Multi-objective handling:
- Scalarize via existing composite score for V1
- Keep raw metrics to upgrade to Pareto front later

Recommended first use:
- Parameter refinement after genetic pre-search

## 1.4 Contextual bandits (online allocation of trials)

Use for deciding which candidate families deserve more budget.

Plan:
- Arm = strategy family or optimizer stream
- Context = dataset regime features + recent batch diagnostics
- Reward = normalized composite score adjusted by confidence
- Policy:
- Start with UCB or Thompson Sampling
- Add min exploration floor

Recommended first use:
- Allocate parallel slots dynamically across candidate groups

## 1.5 Hybrid search policy

Recommended control flow per campaign:

1. Genetic phase explores broadly.
2. Bayesian phase exploits promising regions.
3. Bandit scheduler allocates budget between families/regions each batch.

Stop criteria:
- No meaningful improvement over N batches
- Compute budget exhausted
- Risk constraints repeatedly violated

---

## 2) Parallel execution architecture (multi-process + distributed)

## 2.1 Execution model

Split execution into three services:

1. `Planner`
- Builds batch plan from optimizer suggestions
- Emits immutable `ExperimentJob` records

2. `Dispatcher`
- Places jobs on queue
- Applies priority/quotas

3. `Worker`
- Claims a job lease
- Runs deterministic simulation in isolated process
- Writes artifacts and terminal status atomically

## 2.2 Local multi-process mode

For single-machine development:
- Python multiprocessing (spawn mode)
- Worker count = `min(cpu_cores - 1, configured_max)`
- Per-job temp directory, strict seed pinning
- SQLite write pattern:
- Results written by one writer process or via append-only WAL-safe pattern

## 2.3 Distributed mode

For scale-out:
- Queue abstraction with pluggable backend (Redis, RabbitMQ, or cloud queue)
- Stateless workers using container image + mounted dataset/artifact storage
- Job lease with heartbeat and visibility timeout
- Idempotent completion using `job_id` + `attempt` guard

## 2.4 Fault tolerance

- Retry policy by error class:
- Infra/transient: exponential backoff + capped retries
- Deterministic strategy/runtime errors: mark permanent fail
- Dead-letter queue for repeated failures
- Checkpoint optimizer state at batch boundaries only

## 2.5 Determinism controls in parallel mode

- Job spec hash includes dataset version, code version, params, seed, config
- Worker environment fingerprint recorded (image digest, dependency lock hash)
- Time-dependent calls prohibited inside simulation loop

---

## 3) Compute scheduling for experiment batches

## 3.1 Scheduler responsibilities

- Turn campaign goals into batch DAGs
- Enforce fair share across campaigns
- Handle priority classes (`interactive`, `standard`, `backfill`)
- Respect compute and time budgets

## 3.2 Proposed scheduling policy

- Queue levels:
- L1: interactive smoke batches
- L2: optimization batches
- L3: backfill/repro runs
- Within level: weighted fair queuing by campaign
- Quotas:
- Max concurrent jobs per campaign
- Max daily trial budget
- Max GPU/CPU class usage (future-proof)

## 3.3 Batch lifecycle states

`DRAFT -> QUEUED -> RUNNING -> PARTIAL -> COMPLETED | FAILED | CANCELLED`

- `PARTIAL` means some jobs succeeded and threshold for usable insights reached
- Batch summary computes confidence and recommends continue/stop

## 3.4 Reproducibility in scheduling

- Campaign snapshot created at enqueue time
- Snapshot locks:
- Optimizer state checkpoint
- Strategy registry versions
- Dataset manifest
- Scoring config

---

## 4) Converting to a general-purpose AI Research Platform

## 4.1 Core domain abstraction

Introduce domain-agnostic interfaces:

- `EnvironmentAdapter`: emits state/events and applies actions
- `PolicyAdapter` (strategy): maps state -> action proposals
- `Evaluator`: computes metrics and objective scores
- `ConstraintSet`: validity and safety checks

Trading becomes one adapter implementation, not the platform identity.

## 4.2 Canonical experiment schema

Standardize all experiments (any domain) with:
- `domain`
- `environment_version`
- `policy_id` and `policy_version`
- `parameter_vector`
- `objective_bundle`
- `constraints`
- `seed`
- `artifact_uris`
- `lineage_parent_ids`

## 4.3 Registry and lineage

Add registries:
- Policy registry (versioned)
- Dataset/environment registry (versioned)
- Metric schema registry

Lineage graph tracks:
- Parent candidate(s)
- Optimizer that produced candidate
- Batch/campaign where generated

## 4.4 API surface

Plan minimal service APIs:
- `POST /campaigns`
- `POST /batches/{id}/run`
- `GET /experiments/{id}`
- `GET /lineage/{candidate_id}`
- `POST /reproduce/{experiment_id}`

---

## 5) Applying same system to game economy optimization

## 5.1 Mapping from trading to game economy

- Market replay -> Economy simulation replay
- Strategy -> Economy policy (pricing/reward/drop-rate policy)
- Orders/fills -> Player/system transactions
- Portfolio metrics -> Economy health KPIs

## 5.2 Economy environment adapter

State examples:
- Currency sinks/sources
- Item inventory flows
- Progression speed
- Segment-level player behavior summaries

Action examples:
- Price multipliers
- Reward table coefficients
- Sink intensity settings
- Event cadence parameters

## 5.3 Objective bundle (multi-metric)

Typical objective weights:
- Retention proxy
- Revenue proxy
- Inflation control
- Fairness/stability metrics

Use constrained optimization:
- Hard constraints: no runaway inflation, no pay-to-win threshold breach
- Soft objectives: maximize engagement-adjusted economy health score

## 5.4 Safety workflow

- Offline simulation only in V1
- Counterfactual testing across player cohorts
- Guardrail report generated per batch before any recommendation is accepted

---

## 6) Production-grade orchestration patterns

## 6.1 Workflow orchestration

Use orchestrated workflows for campaign and batch lifecycles:
- Deterministic steps and explicit retries
- Resume from checkpointed state
- Human approval gates for high-cost campaigns

Suitable options: Temporal, Dagster, Prefect, or Argo Workflows.

## 6.2 Data and artifact patterns

- Metadata store: Postgres (preferred) or SQLite for local mode
- Artifact store: object storage with immutable paths
- Event log: append-only status events per job/batch
- Schema evolution with migration discipline

## 6.3 Reliability patterns

- Idempotent handlers everywhere (`request_id`, `job_id`)
- Exactly-once effect by dedupe + atomic state transition
- Circuit breakers for failing worker pools
- Backpressure when queue depth exceeds threshold

## 6.4 Observability and governance

- Metrics: queue latency, success rate, cost per useful result, reproducibility pass rate
- Logs: structured logs with campaign/batch/job correlation IDs
- Traces: planner -> dispatcher -> worker path
- Audit trail: who launched what, with which config, and why

## 6.5 Security and compliance baseline

- Principle of least privilege for workers
- Signed container images
- Immutable experiment records after completion
- Access control for sensitive datasets

---

## Implementation roadmap (planning only)

## Phase 0: Foundations

Deliver:
- Canonical experiment schema
- Job model + queue abstraction
- Deterministic worker harness

Exit criteria:
- Same job run twice yields identical outputs and score

## Phase 1: Parallel local execution

Deliver:
- Multi-process dispatcher/worker
- Batch scheduler with priorities
- Robust persistence of states and artifacts

Exit criteria:
- 100+ experiment batch runs locally with deterministic replay

## Phase 2: Evolution engines

Deliver:
- Genetic optimizer plugin
- Bayesian optimizer plugin
- Bandit budget allocator

Exit criteria:
- Measurable search efficiency gain vs random search baseline

## Phase 3: Distributed execution

Deliver:
- Remote queue backend
- Containerized workers
- Lease/heartbeat/retry/dead-letter handling

Exit criteria:
- Horizontal scale with no duplicate terminal writes

## Phase 4: Platform generalization

Deliver:
- Domain adapter interfaces
- Trading adapter migration to new interfaces
- Lineage and registry services

Exit criteria:
- At least one non-trading domain runs end-to-end

## Phase 5: Game economy package

Deliver:
- Economy simulator adapter
- Economy KPI evaluator
- Guardrail and policy recommendation reports

Exit criteria:
- Stable optimization campaigns on synthetic economy datasets

## Phase 6: Production hardening

Deliver:
- Orchestration engine integration
- SLO dashboards and alerting
- Governance and approval workflow

Exit criteria:
- Meets reliability SLO and reproducibility compliance checks

---

## Immediate planning outputs to create next

1. `docs/specs/experiment_job_schema.md`
2. `docs/specs/optimizer_plugin_contract.md`
3. `docs/specs/scheduler_policy.md`
4. `docs/specs/domain_adapter_contract.md`
5. `docs/specs/game_economy_objective_bundle.md`
6. `docs/runbooks/worker_failure_modes.md`

These are the highest-leverage specs before implementation starts.
