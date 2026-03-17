# Task 01 — Bayesian TPE Optimizer

## Status
Pending

## Owner
Codex agent

## Context

`meta/optimizers/bayesian.py` currently contains a stub that returns the same midpoint defaults on every call to `suggest()` and ignores all observations. The platform cannot learn anything using this optimizer.

The `Optimizer` interface (`meta/optimizers/base.py`):

```python
class Optimizer(ABC):
    def suggest(self, *, iteration: int, batch_size: int) -> list[Candidate]: ...
    def observe(self, *, scored_candidates: list[tuple[Candidate, float]]) -> None: ...
    def checkpoint(self) -> dict[str, Any]: ...
    def restore(self, state: dict[str, Any]) -> None: ...
```

`Candidate` is a frozen dataclass: `candidate_id: str`, `parameters: dict[str, Any]`.

The `factory.py` already instantiates `BayesianOptimizer`:
```python
if name == "bayesian":
    defaults = {key: (bounds[0] + bounds[1]) // 2 for key, bounds in search_space.items()}
    ...
    return BayesianOptimizer(defaults=defaults)
```

The factory signature will need to change to pass `search_space` and `seed` instead of `defaults`.

## Task

### 1. Implement TPE in `meta/optimizers/bayesian.py`

Replace the stub with a Tree-structured Parzen Estimator (TPE) that:

1. **Warm-up phase** (first `n_startup_trials` candidates): sample uniformly at random from the integer search space using a seeded RNG. Default `n_startup_trials = 10`.
2. **TPE phase** (after warm-up): split observed candidates into "good" (top `gamma` fraction, default `gamma = 0.25`) and "bad" (the rest). For each parameter independently, fit a histogram/KDE over the good and bad sets. Sample from good, score by `l(x) / g(x)`, return top candidates.
3. For integer parameters (all parameters in this system are integers), use a discrete KDE: add ±1 neighbourhood smoothing around each observed value, clipped to `[lo, hi]`.

**Implementation constraints:**
- Standard library + `random` only. No `scipy`, `numpy`, or external TPE libraries.
- All randomness must go through `self._rng = random.Random(seed)`.
- The optimizer must be deterministic: same seed + same observations → same suggestions.
- Keep the `_ORDERED_PAIRS` constraint from `GeneticOptimizer` if parameter pairs `(fast_window, slow_window)` or `(fast_period, slow_period)` are present in the search space. Copy the enforcement logic.

**Signature:**
```python
class BayesianOptimizer(Optimizer):
    def __init__(
        self,
        *,
        search_space: dict[str, tuple[int, int]],
        seed: int,
        n_startup_trials: int = 10,
        gamma: float = 0.25,
    ) -> None: ...
```

**`suggest()`**: returns exactly `batch_size` candidates with IDs `"bo-{counter:05d}"`.

**`observe()`**: appends `(parameters, score)` pairs to the internal history.

**`checkpoint()`**: returns a JSON-serialisable dict containing:
- `"history"`: list of `{"params": {...}, "score": float}` dicts
- `"counter"`: int

**`restore(state)`**: re-populates history and counter from checkpoint dict.

### 2. Update `meta/optimizers/factory.py`

Change the `"bayesian"` branch to pass `search_space` and `seed` instead of `defaults`:

```python
if name == "bayesian":
    return BayesianOptimizer(search_space=search_space, seed=seed)
```

Remove the `defaults`-construction logic and the `fast_window`/`slow_window` special-case (the optimizer handles ordering internally now).

### 3. Write unit tests in `tests/unit/test_bayesian_optimizer.py`

```python
def test_warm_up_returns_random_candidates():
    # First n_startup_trials suggestions must differ from each other
    # (not identical midpoints)

def test_post_warmup_exploits_good_region():
    # After observing that high fast_window scores better,
    # post-warmup suggestions should skew toward higher fast_window values
    # (probabilistic — run enough candidates to make this reliable)

def test_determinism():
    # Two optimizers with same seed + same observations → identical suggestion lists

def test_checkpoint_restore_roundtrip():
    # Run 15 iterations, checkpoint, restore into fresh instance, assert suggest() output matches

def test_ordered_pairs_enforced():
    # With search_space = {"fast_window": (2, 10), "slow_window": (5, 20)},
    # all suggestions must have slow_window > fast_window
```

## Acceptance Criteria

- [ ] `BayesianOptimizer.__init__` takes `search_space`, `seed` (no `defaults`)
- [ ] `factory.py` updated to pass `search_space` and `seed`
- [ ] Warm-up phase: first 10 suggestions are random, not midpoints
- [ ] Post-warmup: `suggest()` returns candidates informed by observation history
- [ ] Determinism: same seed + same observations → identical output
- [ ] `checkpoint()` / `restore()` roundtrip works
- [ ] `uv run pytest tests/unit/test_bayesian_optimizer.py` passes

## Files to Create

- `tests/unit/test_bayesian_optimizer.py`

## Files to Modify

- `meta/optimizers/bayesian.py` (replace stub)
- `meta/optimizers/factory.py` (update bayesian branch)

## Files to NOT Touch

- `meta/optimizers/base.py`
- `meta/optimizers/genetic.py`
- `meta/optimizers/bandit.py`
- `domains/`
- `core/`
- `persistence/`
- Any spec files
