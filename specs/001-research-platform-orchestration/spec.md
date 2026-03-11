# Feature Specification: Research Platform Orchestration Baseline

**Feature Branch**: `001-research-platform-orchestration`  
**Created**: 2026-03-11  
**Status**: Draft  
**Input**: User description: "setup github/spec-kit, initialize the spec docs. create implementation doc, tasks"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Campaign Lifecycle and Strategy Evolution (Priority: P1)

As a research operator, I can define and run experiment campaigns that evolve candidates using genetic, Bayesian, and bandit methods so that search decisions are systematic and reproducible.

**Why this priority**: This is the core value engine for experimentation and directly enables autonomous improvement loops.

**Independent Test**: Create a campaign with fixed seed and budget, run two full batches, and verify that candidate suggestions, rankings, and transitions are identical across reruns.

**Acceptance Scenarios**:

1. **Given** a search-space definition and optimizer policy, **When** a campaign is started, **Then** the system generates a deterministic candidate set per batch.
2. **Given** completed experiment results, **When** optimizer `observe` is called, **Then** optimizer state advances and is checkpointed with reproducible metadata.

---

### User Story 2 - Parallel Batch Execution and Compute Scheduling (Priority: P1)

As a platform operator, I can run experiment jobs in parallel with explicit scheduling policies so compute is used efficiently without violating fairness or reproducibility guarantees.

**Why this priority**: Experiment throughput and reliable scaling are required before broader platform expansion.

**Independent Test**: Queue mixed-priority jobs, run with multiple workers, and verify lease/retry/idempotency behavior and final state consistency.

**Acceptance Scenarios**:

1. **Given** queued jobs in multiple priority classes, **When** dispatcher schedules work, **Then** jobs are selected according to weighted fair policy and quota constraints.
2. **Given** a worker crash mid-execution, **When** lease expires, **Then** job retries follow policy and produce at most one terminal persisted result.

---

### User Story 3 - Domain Generalization and Game Economy Reuse (Priority: P2)

As a research lead, I can run the same orchestration core against non-trading environments, including game economy simulation, by plugging in domain adapters and objective bundles.

**Why this priority**: General-purpose applicability is a strategic goal but depends on stable orchestration foundations.

**Independent Test**: Execute one trading and one game-economy campaign through the same orchestration interfaces and produce comparable experiment artifacts.

**Acceptance Scenarios**:

1. **Given** a domain adapter implementing the platform contract, **When** a campaign runs, **Then** the orchestrator executes without trading-specific assumptions.
2. **Given** game economy objective/guardrail config, **When** scoring runs, **Then** it outputs objective and constraint evaluation for optimization decisions.

---

### User Story 4 - Production-Grade Operations and Governance (Priority: P3)

As an engineering owner, I can observe, audit, and recover orchestration workflows with production-grade reliability patterns.

**Why this priority**: Essential for long-term operation, but can follow core functionality.

**Independent Test**: Trigger failures, cancellations, and resume flows and verify traces, audit records, and recovery outcomes meet policy.

**Acceptance Scenarios**:

1. **Given** an orchestration failure, **When** retry and resume logic executes, **Then** state recovery preserves lineage and avoids duplicate terminal writes.
2. **Given** a completed campaign, **When** audit data is queried, **Then** actor, config, artifact, and lineage records are complete and immutable.

---

### Edge Cases

- What happens when optimizer proposes invalid parameter combinations that violate constraints?
- How does scheduler behave when all campaigns exceed quota but one is `interactive` priority?
- What happens if two workers race to complete the same leased job?
- How is determinism handled when dependency versions differ across workers?
- What happens when a batch is partially successful and termination criteria is ambiguous?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a canonical `ExperimentJob` schema containing dataset/environment version, policy/strategy version, parameter vector, seed, objective bundle, constraints, and lineage fields.
- **FR-002**: System MUST support optimizer plugins with deterministic `suggest`, `observe`, `checkpoint`, and `restore` operations.
- **FR-003**: System MUST support three search methods in orchestration policy: genetic, Bayesian, and contextual bandit allocation.
- **FR-004**: System MUST expose campaign and batch lifecycle state machines with explicit transitions and terminal states.
- **FR-005**: System MUST support local multi-process workers and distributed worker mode via a queue abstraction.
- **FR-006**: System MUST enforce scheduling with priority classes, fair-share policy, and per-campaign quotas.
- **FR-007**: System MUST implement lease/heartbeat/retry/dead-letter semantics for job reliability.
- **FR-008**: System MUST guarantee idempotent terminal persistence for each `job_id` attempt pair.
- **FR-009**: System MUST record reproducibility fingerprints (code version, dependency lock hash/image digest, config hash, seed).
- **FR-010**: System MUST define domain adapter interfaces to decouple orchestration from trading-specific logic.
- **FR-011**: System MUST provide a game economy adapter specification including state, actions, objectives, and guardrails.
- **FR-012**: System MUST produce observability outputs for campaign/batch/job with correlation IDs (metrics, logs, traces).
- **FR-013**: System MUST maintain immutable audit records for launch parameters, actor identity, and artifact lineage.
- **FR-014**: System MUST support safe resume from last committed orchestration checkpoint after interruption.

### Key Entities *(include if feature involves data)*

- **Campaign**: Long-lived optimization run with objective, budget, policy, and status.
- **Batch**: Coordinated set of experiment jobs within one campaign iteration.
- **ExperimentJob**: Immutable executable unit with full reproducibility metadata.
- **OptimizerState**: Versioned snapshot of search method state.
- **SchedulerPolicy**: Priority/fairness/quota rules used by dispatcher.
- **WorkerLease**: Time-bound claim on a job with heartbeat and attempt counters.
- **ExperimentResult**: Metrics, score, artifacts, runtime status, and diagnostics.
- **DomainAdapter**: Environment/policy/evaluator contract for a specific research domain.
- **LineageRecord**: Parent-child relations between generated candidates and outcomes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Re-running the same campaign snapshot with identical seeds reproduces candidate generation and composite ranking with 100% equality.
- **SC-002**: In local multi-process mode, a 100-job batch completes with no duplicate terminal writes and >= 95% success on valid jobs.
- **SC-003**: Scheduler enforces configured priority and quota policies with zero starvation for non-paused campaigns over a 24h synthetic workload.
- **SC-004**: At least one non-trading domain (game economy simulation) runs end-to-end using the shared orchestration interfaces.
- **SC-005**: Failure recovery resumes from latest checkpoint with no loss of completed experiment history.
