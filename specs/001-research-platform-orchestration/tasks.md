# Tasks: Research Platform Orchestration Baseline

**Input**: Design documents from `/specs/001-research-platform-orchestration/`
**Prerequisites**: `plan.md`, `spec.md`, plus artifacts defined in this task list

## Format: `[ID] [P?] [Story] Description`

- `[P]`: Can run in parallel (different files, no blocking dependency)
- `[Story]`: `US1`, `US2`, `US3`, `US4`

## Status Summary

- Completed: `40`
- Remaining: `19`
- Current focus: close docs (`T041`-`T045`), then implement full agent runtime + self-learning loop (`T046`-`T059`)

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Create module directory skeleton in `core/`, `meta/`, `persistence/`, `domains/`, `observability/`, `tests/`
- [x] T002 Add package markers and baseline init files in `core/__init__.py`, `meta/__init__.py`, `domains/__init__.py`
- [x] T003 [P] Create documentation stubs: `specs/001-research-platform-orchestration/research.md`, `data-model.md`, `quickstart.md`
- [x] T004 [P] Create contracts directory and initial files under `specs/001-research-platform-orchestration/contracts/`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T005 Define canonical orchestration entities in `persistence/models.py`
- [x] T006 Implement state machine enums/transitions in `core/orchestration/state_machine.py`
- [x] T007 [P] Implement reproducibility fingerprint utilities in `core/reproducibility/fingerprint.py`
- [x] T008 [P] Implement campaign snapshot serialization in `core/reproducibility/snapshot.py`
- [x] T009 Implement idempotent terminal write guard in `persistence/repositories.py`
- [x] T010 Configure migration baseline (SQLite schema init + backward-compatible `ALTER TABLE` in `persistence/repositories.py`)

**Checkpoint**: Foundation complete; user story implementation can proceed.

---

## Phase 3: User Story 1 - Campaign Lifecycle and Strategy Evolution (Priority: P1) 🎯

**Goal**: Deterministic campaign lifecycle and optimizer plugin system.

**Independent Test**: Repeat same campaign snapshot twice and confirm identical optimizer outputs and batch decisions.

### Tests for User Story 1

- [x] T011 [P] [US1] Add deterministic campaign replay test in `tests/deterministic/test_campaign_replay.py`
- [x] T012 [P] [US1] Add optimizer contract test in `tests/unit/test_optimizer_contract.py`

### Implementation for User Story 1

- [x] T013 [US1] Implement optimizer base contract in `meta/optimizers/base.py`
- [x] T014 [P] [US1] Implement genetic optimizer skeleton in `meta/optimizers/genetic.py`
- [x] T015 [P] [US1] Implement Bayesian optimizer skeleton in `meta/optimizers/bayesian.py`
- [x] T016 [P] [US1] Implement bandit allocator skeleton in `meta/optimizers/bandit.py`
- [x] T017 [US1] Implement campaign orchestration aggregate in `core/orchestration/campaign.py`
- [x] T018 [US1] Implement batch composition logic in `core/orchestration/batch.py`

**Checkpoint**: US1 fully testable and deterministic.

---

## Phase 4: User Story 2 - Parallel Execution and Scheduling (Priority: P1)

**Goal**: Run jobs in parallel with fair scheduling and reliable retries.

**Independent Test**: Mixed-priority queue run demonstrates policy compliance, retries, and no duplicate terminal records.

### Tests for User Story 2

- [x] T019 [P] [US2] Add scheduler policy tests in `tests/unit/test_scheduler_policy.py`
- [x] T020 [P] [US2] Add lease/retry integration tests in `tests/integration/test_retry_deadletter.py`

### Implementation for User Story 2

- [x] T021 [US2] Implement planner job emission in `core/execution/planner.py`
- [x] T022 [US2] Implement dispatcher queue + policy application in `core/execution/dispatcher.py`
- [x] T023 [US2] Implement lease heartbeat flow in execution loop (`core/execution/dispatcher.py`, `core/execution/lease.py`)
- [x] T024 [P] [US2] Implement lease model helpers in `core/execution/lease.py`
- [x] T025 [P] [US2] Implement priority/fair-share policy in `core/scheduling/policy.py`
- [x] T026 [P] [US2] Implement queue primitives in `core/scheduling/priority_queue.py`
- [x] T027 [P] [US2] Implement per-campaign quotas in `core/scheduling/quotas.py`

**Checkpoint**: US2 policy and reliability behavior validated.

---

## Phase 5: User Story 3 - Domain Generalization and Game Economy Reuse (Priority: P2)

**Goal**: Introduce domain-neutral adapters and apply to game economy optimization.

**Independent Test**: Trading and game-economy campaigns run through same orchestration interfaces.

### Tests for User Story 3

- [x] T028 [P] [US3] Add adapter contract tests in `tests/unit/test_domain_adapter_contract.py`
- [x] T029 [P] [US3] Add cross-domain orchestration integration test in `tests/integration/test_cross_domain_campaign.py`

### Implementation for User Story 3

- [x] T030 [US3] Define adapter interfaces in `domains/base.py`
- [x] T031 [US3] Implement trading adapter wrapper in `domains/trading/adapter.py`
- [x] T032 [US3] Implement game economy adapter in `domains/game_economy/adapter.py`
- [x] T033 [US3] Implement game economy objectives/guardrails in `domains/game_economy/objectives.py`

**Checkpoint**: US3 reusable architecture validated.

---

## Phase 6: User Story 4 - Production Operations and Governance (Priority: P3)

**Goal**: Add observability, auditability, and crash-safe resume behavior.

**Independent Test**: Crash/restart scenario recovers from checkpoint with complete audit trails.

### Tests for User Story 4

- [x] T034 [P] [US4] Add recovery/resume integration test in `tests/integration/test_resume_recovery.py`
- [x] T035 [P] [US4] Add audit/lineage integrity test in `tests/integration/test_audit_lineage.py`

### Implementation for User Story 4

- [x] T036 [US4] Implement structured logging context helpers in `observability/logging.py`
- [x] T037 [P] [US4] Implement orchestration metrics emitters in `observability/metrics.py`
- [x] T038 [P] [US4] Implement trace correlation helpers in `observability/tracing.py`
- [x] T039 [US4] Add audit event repository support in `persistence/repositories.py`
- [x] T040 [US4] Add orchestrator resume service in `core/orchestration/resume.py`

**Checkpoint**: US4 production-readiness baseline complete.

---

## Phase 7: Polish & Validation

- [ ] T041 [P] Finalize `research.md` with explicit technology decisions and tradeoffs
- [ ] T042 [P] Finalize `data-model.md` with entity diagrams and constraints
- [ ] T043 [P] Finalize `contracts/optimizer-api.md`, `contracts/scheduler-api.md`, `contracts/domain-adapter-api.md`
- [ ] T044 [P] Finalize `quickstart.md` with local deterministic run instructions
- [ ] T045 Run complete test suite and document deterministic replay proof in `specs/001-research-platform-orchestration/research.md`

---

## Phase 8: Agent Runtime Loop (Designer/Implementer/Reviewer)

- [ ] T046 Define persistent schemas for `StrategyProposal`, `StrategyImplementation`, `ReviewResult` in `persistence/models.py`
- [ ] T047 Add repositories for proposal/implementation/review artifacts in `persistence/repositories.py`
- [ ] T048 Implement `DesignerAgent` service in `agents/designer.py`
- [ ] T049 Implement `ImplementerAgent` service in `agents/implementer.py`
- [ ] T050 Implement `ReviewerAgent` service in `agents/reviewer.py`
- [ ] T051 Implement role pipeline orchestrator in `agents/pipeline.py`
- [ ] T052 [P] Add happy-path pipeline integration test in `tests/integration/test_agent_pipeline_happy_path.py`
- [ ] T053 [P] Add rejection-path integration test in `tests/integration/test_agent_pipeline_rejection_path.py`
- [ ] T054 [P] Add parallel/idempotency pipeline test in `tests/integration/test_agent_pipeline_parallel_idempotency.py`

---

## Phase 9: Autonomous Self-Learning Loop (Trading)

- [ ] T055 Implement persistent memory state manager in `agents/memory.py`
- [ ] T056 Implement loop controller (`analyze -> propose -> implement -> review -> execute -> score -> update`) in `agents/loop_controller.py`
- [ ] T057 Implement exploration/exploitation policy controls in `agents/policies/exploration_exploitation.py`
- [ ] T058 Implement safety guards for strategy generation/execution in `agents/guards/safety.py`
- [ ] T059 Add trading loop runner and end-to-end tests in `tests/deterministic/test_agentic_loop_replay.py`, `tests/integration/test_agentic_loop_trading_end_to_end.py`, `tests/integration/test_agentic_loop_resume.py`

---

## Dependencies & Execution Order

- T001-T004 before all other tasks.
- T005-T010 block all user stories.
- US1 and US2 can begin after foundational tasks complete; US2 consumes job/state artifacts from US1.
- US3 depends on stable orchestration interfaces from US1/US2.
- US4 depends on orchestration and persistence capabilities from prior stories.
- T041-T045 run after core implementation tasks.
- T046-T054 depend on US1-US4 and should start after T041-T045.
- T055-T059 depend on completion of T046-T054.

## Implementation Strategy

1. Ship MVP with Phase 1-3 (campaign lifecycle + optimizer contract).
2. Add scalable throughput with Phase 4 (execution + scheduler).
3. Enable non-trading reuse with Phase 5 (adapter abstraction + game economy).
4. Harden for production with Phase 6, then finalize docs in Phase 7.
5. Build agent runtime loop (Phase 8), then full autonomous self-learning cycle (Phase 9).
