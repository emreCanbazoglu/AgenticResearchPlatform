# Task 02 — Bandit UCB1 Optimizer

## Status
Pending

## Owner
Codex agent

## Context

`meta/optimizers/bandit.py` currently contains a `BanditAllocator` class that:
- Is NOT a subclass of `Optimizer`
- Has a completely different interface (`observe(arm, reward)` / `average_reward(arm)`)
- Is not registered in `meta/optimizers/factory.py`
- Cannot be used by the orchestration engine

This class needs to be replaced with a proper `BanditOptimizer` that implements the `Optimizer` protocol.

The `Optimizer` interface (`meta/optimizers/base.py`):

```python
class Optimizer(ABC):
    def suggest(self, *, iteration: int, batch_size: int) -> list[Candidate]: ...
    def observe(self, *, scored_candidates: list[tuple[Candidate, float]]) -> None: ...
    def checkpoint(self) -> dict[str, Any]: ...
    def restore(self, state: dict[str, Any]) -> None: ...
```

The factory (`meta/optimizers/factory.py`) currently only supports `"genetic"` and `"bayesian"`. This task adds `"bandit"`.

## Algorithm: UCB1 with Fixed Candidate Pool

The bandit optimizer treats hyperparameter optimization as a finite-arm bandit problem:

1. **Initialization**: sample `pool_size` (default 100) random candidate parameter sets from the integer search space using a seeded RNG. These become the fixed "arms".
2. **`suggest()`**: for each arm compute the UCB1 score:
   ```
   ucb1(arm) = mean_reward(arm) + C * sqrt(log(total_pulls + 1) / (pulls(arm) + 1))
   ```
   where `C` is the exploration coefficient (default `1.0`). Return the top `batch_size` arms by UCB1 score as `Candidate` objects. Arms that have never been pulled are scored as `+inf` (prioritize exploration of untried arms first).
3. **`observe()`**: for each `(candidate, score)` pair, update `pulls` and `sum_reward` for the matching arm. Match by `candidate_id`.
4. **Ordering constraint**: same `_ORDERED_PAIRS` enforcement as `GeneticOptimizer` — if `(fast_window, slow_window)` or `(fast_period, slow_period)` are both present, enforce `slow > fast`.

**Signature:**
```python
class BanditOptimizer(Optimizer):
    def __init__(
        self,
        *,
        search_space: dict[str, tuple[int, int]],
        seed: int,
        pool_size: int = 100,
        exploration_coeff: float = 1.0,
    ) -> None: ...
```

**`suggest()`**: returns exactly `batch_size` candidates. Always returns from the fixed pool — never generates new candidates after init. Candidate IDs are `"bandit-{pool_index:05d}"`.

**`observe()`**: updates internal reward tracking for matched candidates only (by `candidate_id`). Unknown IDs are silently ignored.

**`checkpoint()`**: returns a JSON-serialisable dict:
```json
{
  "pool": [{"candidate_id": "...", "parameters": {...}}, ...],
  "pulls": {"bandit-00000": 3, ...},
  "sum_rewards": {"bandit-00000": 1.25, ...}
}
```

**`restore(state)`**: restores pool, pulls, and sum_rewards from checkpoint.

## Task

### 1. Replace `meta/optimizers/bandit.py`

Remove the `BanditAllocator` class entirely. Implement `BanditOptimizer` as described above.

### 2. Update `meta/optimizers/factory.py`

Add the `"bandit"` branch:
```python
if name == "bandit":
    return BanditOptimizer(search_space=search_space, seed=seed)
```

Import `BanditOptimizer` at the top.

### 3. Write unit tests in `tests/unit/test_bandit_optimizer.py`

```python
def test_pool_initialized_with_correct_size():
    # BanditOptimizer with pool_size=20 → suggest() never returns > 20 unique candidates

def test_untried_arms_selected_first():
    # Before any observations, suggest() should return arms not yet pulled

def test_ucb_exploits_after_observations():
    # After observing that certain arms have high rewards,
    # those arms should appear more frequently in subsequent suggest() calls

def test_determinism():
    # Two BanditOptimizers with same seed → identical pool and identical suggest() output
    # given identical observations

def test_checkpoint_restore_roundtrip():
    # Run 5 iterations with observations, checkpoint, restore to fresh instance,
    # assert suggest() output matches

def test_ordered_pairs_enforced_in_pool():
    # All candidates in pool must satisfy slow_window > fast_window (when both present)

def test_suggest_returns_exact_batch_size():
    # suggest(iteration=0, batch_size=5) returns exactly 5 candidates
```

## Acceptance Criteria

- [ ] `BanditAllocator` is removed; `BanditOptimizer` is the only class in the file
- [ ] `BanditOptimizer` is a proper subclass of `Optimizer`
- [ ] `factory.py` registers `"bandit"` and imports `BanditOptimizer`
- [ ] UCB1 formula is implemented correctly
- [ ] Untried arms scored as `+inf` so they're explored first
- [ ] Determinism: same seed → same pool → same suggestions given same observations
- [ ] `checkpoint()` / `restore()` roundtrip works
- [ ] `uv run pytest tests/unit/test_bandit_optimizer.py` passes

## Files to Create

- `tests/unit/test_bandit_optimizer.py`

## Files to Modify

- `meta/optimizers/bandit.py` (replace `BanditAllocator` with `BanditOptimizer`)
- `meta/optimizers/factory.py` (add `"bandit"` branch)

## Files to NOT Touch

- `meta/optimizers/base.py`
- `meta/optimizers/genetic.py`
- `meta/optimizers/bayesian.py`
- `domains/`
- `core/`
- `persistence/`
- Any spec files
