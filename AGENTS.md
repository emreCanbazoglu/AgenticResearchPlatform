# AGENTS.md

## Project Overview

**Agentic Research Platform** — a deterministic, offline-first system for autonomous strategy discovery and evaluation via historical replay. The primary domain is trading, with a generalized architecture supporting other domains (e.g. game economy optimization).

This is a **research platform**, not a production trading system. Profitability is not a success criterion.

## Development Model

**Codex is the sole director of this project.** It owns:
- Project management (task breakdown, prioritization, sequencing)
- Architecture and design decisions
- Code review and approval of all changes
- Spec authoring and validation

**OpenAI Codex agents handle implementation.** Codex spawns them via CLI to execute well-defined tasks, then reviews their output before merging.

### Workflow

1. Codex breaks work into a scoped task with clear inputs, outputs, and acceptance criteria.
2. Codex spawns a Codex agent via CLI: `codex "<task description>"` (or with `--approval-mode auto-edit` for autonomous runs).
3. Codex implements the task on a branch.
4. Codex reviews the diff, runs tests, and either approves or sends back with revision notes.
5. Codex merges approved work and updates project state.

### Division of Responsibilities

| Responsibility | Owner |
|---|---|
| Spec writing | Codex |
| Task decomposition | Codex |
| Architecture decisions | Codex |
| Implementation | Codex agent |
| Code review | Codex |
| Test validation | Codex |
| Merge approval | Codex |

Codex agents are stateless implementers — they receive a task, produce code, and return. They do not make architectural decisions or modify specs.

## Running the Project

```bash
# Run a demo campaign
uv run python run_mvp.py

# Run tests
uv run pytest
```

No external APIs or network access required. All execution is offline.

## Key Design Principles

- **Deterministic execution** — identical inputs must always produce identical outputs and scores. Random seeds must be pinned and propagated.
- **Offline-first** — no external APIs, no network calls inside simulation loops.
- **Reproducible experiments** — every experiment stores dataset version, strategy version, parameters, seed, and system config.
- **No global mutable state** — strategies and domain adapters must be stateless or explicitly stateful; no side effects.
- **Strategy-agnostic architecture** — the core orchestration layer is domain-independent.

## Architecture

The system has 8 simulation layers plus 3 cross-cutting planes:

### Core Layers
1. **Market Replay** — loads historical OHLCV data, emits time-ordered events, maintains simulated clock
2. **Strategy Layer** — deterministic, parameterizable decision logic
3. **Execution Simulator** — fills orders, applies commission/slippage, generates fill events
4. **Portfolio Simulator** — tracks cash, positions, equity, PnL, drawdown
5. **Scoring Engine** — computes raw metrics, risk metrics, and composite score
6. **Experiment Runner** — orchestrates full simulations end-to-end
7. **Meta Controller** — selects/evolves strategies, coordinates batches
8. **Persistence Layer** — SQLite storage for all experiment data

### Cross-Cutting Planes (from planning)
- **Search Plane** (`meta/optimizers/`) — genetic, Bayesian, bandit optimizers
- **Compute Plane** (`core/execution/`) — job queueing, dispatcher, workers, leasing, retries
- **Platform Plane** (`domains/`, `persistence/`) — domain adapters, lineage, registry

## Module Map

```
run_mvp.py                    # Entry point — runs a CampaignConfig
core/
  orchestration/
    campaign.py               # run_campaign() — top-level loop
    batch.py                  # BatchSummary
    state_machine.py          # CampaignStatus enum
    resume.py                 # Resume logic
  execution/
    planner.py                # build_jobs() — BatchContext -> [ExperimentJob]
    dispatcher.py             # dispatch_jobs() — parallel job execution
    worker.py                 # execute_job() — runs one simulation
    adapters.py               # get_adapter(domain) — domain adapter registry
    lease.py                  # Job lease management
  reproducibility/
    snapshot.py               # CampaignSnapshot + fingerprint()
  scheduling/                 # Scheduling policies (planned)
domains/
  base.py                     # EnvironmentAdapter, RunResult base classes
  trading/
    adapter.py                # Trading domain adapter
    strategies/               # Strategy implementations
  game_economy/
    adapter.py                # Game economy domain adapter
    objectives.py             # Economy KPI evaluator
meta/
  optimizers/
    base.py                   # Optimizer base class + Candidate type
    factory.py                # make_optimizer(name, ...)
    genetic.py                # Genetic search optimizer
    bayesian.py               # Bayesian (TPE) optimizer
    bandit.py                 # Contextual bandit budget allocator
scoring/
  metrics.py                  # Raw + risk metric computation
persistence/
  models.py                   # ExperimentJob, ExperimentResult, CampaignRecord, etc.
  repositories.py             # SqliteExperimentRepository
observability/
  logging.py                  # Structured logging
  metrics.py                  # Metric emission
  tracing.py                  # new_trace_id(), correlation IDs
tests/
  unit/                       # Unit tests
  integration/                # Integration tests
  deterministic/              # Determinism regression tests
```

## Adding a New Domain

1. Create `domains/<domain>/adapter.py` implementing `EnvironmentAdapter` from `domains/base.py`
2. Register it in `core/execution/adapters.py` via `get_adapter()`
3. Add a default search space in `core/orchestration/campaign.py`'s `default_spaces`

## Strategy Interface Contract

All strategies must implement:
- `initialize(context)` — called once before simulation
- `on_candle(candle)` — called for each OHLCV data point
- `generate_orders()` — returns list of `{side, quantity, order_type}` orders
- `on_fill(fill)` — called when an order executes
- `finalize()` — called after simulation ends

Constraints: no external API calls, no global state, deterministic behavior.

## Optimizer Interface Contract

All optimizers in `meta/optimizers/` must implement:
- `suggest(iteration, batch_size) -> list[Candidate]`
- `observe(scored_candidates: list[tuple[Candidate, float]])`
- `checkpoint() -> bytes`
- `restore(bytes)`

## Campaign Lifecycle States

`DRAFT -> QUEUED -> RUNNING -> PARTIAL -> COMPLETED | FAILED | CANCELLED`

`PARTIAL` = some jobs succeeded, usable insights available.

## Persistence

- SQLite (`experiments.sqlite` by default)
- Tables: campaigns, batches, experiment jobs, experiment results, audit events, checkpoints
- Checkpoints saved at each batch boundary for resume support
- Resume via `CampaignConfig(resume_from_latest=True)`

## Scoring

Composite score formula (weights from `config/scoring.yaml`):
```
score = w1 * normalized_return + w2 * normalized_sharpe - w3 * normalized_drawdown + w4 * normalized_trade_count
```

Raw metrics: total return, annualized return, trade count, win rate.
Risk metrics: max drawdown, volatility, Sharpe ratio.

## Implementation Status

| Component | Status | Notes |
|---|---|---|
| Campaign orchestration | Complete | Deterministic, resumable, checkpoint/resume |
| Parallel execution (local) | Complete | ProcessPoolExecutor, retry, dead-letter |
| Genetic optimizer | Complete | Elite-based mutation, seeded; supports MA/RSI/MACD param spaces |
| Bayesian optimizer | Complete | TPE (discrete KDE, gamma=0.25, 10-trial warm-up); deterministic |
| Bandit allocator | Complete | UCB1 optimizer subclass; fixed pool of 100 arms; registered as "bandit" |
| Trading domain adapter | Complete | MA crossover, RSI, MACD; CSV replay; commission model; walk-forward split |
| Risk metrics | Complete | Sharpe, max drawdown, volatility, win rate, composite score |
| config/scoring.yaml | Complete | Crypto-tuned weights (return 0.4, sharpe 0.4, drawdown 0.2) |
| BTC/ETH historical data | Complete | 1000-row real OHLCV from Binance in data/trading/ |
| Walk-forward split | Complete | train_ratio=0.7 default in run_mvp.py; optimizer on train, metrics on test |
| Game economy adapter | Stub | Trivial balance formula — no real simulator |
| Game economy objectives | Stub | Single inflation guardrail only |
| Audit & lineage | Complete | Full trace_id propagation |
| SQLite persistence | Complete | Schema migrations, idempotent writes |
| State machine | Complete | Full lifecycle transition validation |
| Observability | Partial | Logging + tracing work; MetricsCollector unused |
| Distributed workers | Not started | Local-only for now |
| data/game_economy/ | Missing | No sample data for game economy domain |

### Phase Completion
- **Phase 0 (Foundations)**: Complete
- **Phase 1 (Parallel local execution)**: Complete
- **Phase 2 (Evolution engines)**: Complete — genetic, Bayesian (TPE), bandit (UCB1) all implemented
- **Crypto Trading V1** (`specs/002-crypto-trading-v1/`): Complete — 32/32 tests passing
- **Optimizer Quality** (`specs/003-optimizers/`): Complete — TPE + UCB1; 51/51 tests passing
- **Real Data + Walk-Forward** (`specs/004-real-data-walkforward/`): Complete — real Binance data; walk-forward split
- **Phase 3 (Distributed execution)**: Not started
- **Phase 4 (Platform generalization)**: Partially done (domain adapter pattern in place)
- **Phase 5 (Game economy)**: Stub only
- **Phase 6 (Production hardening)**: Not started

## Known Spec Deviations

These are intentional simplifications made during the MVP — track before closing out each phase:

- **Optimizer interface**: Spec (`RESEARCH_PLATFORM_PLANNING.md`) calls for `suggest(batch_context)` with constraints/budgets. Code uses `suggest(iteration, batch_size)`. Constraints cannot currently be passed to optimizers.
- **Scoring**: `SCORING_SPEC.md` specifies 4+ metrics; only profitability implemented.
- **Meta Controller**: `META_CONTROLLER_SPEC.md` specifies a separate module; logic is embedded in `campaign.py`.
- **Agentic loop**: `AGENTIC_LOOP_SPEC.md` specifies an explicit memory structure and validation gate; current loop is simpler (suggest → execute → observe).

## Specs and Planning Docs

| File | Purpose |
|---|---|
| `README.md` | Project purpose and non-goals |
| `ARCHITECTURE.md` | Layer responsibilities |
| `STRATEGY_API.md` | Strategy interface contract |
| `SCORING_SPEC.md` | Metrics and composite score formula |
| `EXPERIMENT_PROTOCOL.md` | Experiment execution and reproducibility |
| `AGENTIC_LOOP_SPEC.md` | Autonomous iteration cycle definition |
| `AGENT_WORKFLOW.md` | Designer / Implementer / Reviewer agent roles |
| `META_CONTROLLER_SPEC.md` | Strategy selection and evolution |
| `RESEARCH_PLATFORM_PLANNING.md` | Full architecture evolution blueprint |
| `NEXT_STEPS.md` | Immediate next specs to write before coding |
| `PROJECT_STRUCTURE.md` | Directory layout overview |
| `specs/` | Detailed specs per component (WIP) |
