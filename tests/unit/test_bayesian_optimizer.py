from __future__ import annotations

from meta.optimizers.bayesian import BayesianOptimizer
from meta.optimizers.base import Candidate


def test_warm_up_returns_random_candidates() -> None:
    optimizer = BayesianOptimizer(
        search_space={"fast_window": (2, 10), "slow_window": (5, 20)},
        seed=42,
        n_startup_trials=10,
    )

    candidates = optimizer.suggest(iteration=0, batch_size=10)
    params = [tuple(sorted(candidate.parameters.items())) for candidate in candidates]

    assert len(set(params)) > 1


def test_post_warmup_exploits_good_region() -> None:
    optimizer = BayesianOptimizer(
        search_space={"fast_window": (2, 10), "slow_window": (5, 20)},
        seed=7,
        n_startup_trials=10,
    )

    # Build warm-up history biased toward high fast_window values.
    for i in range(10):
        candidate = Candidate(
            candidate_id=f"seed-{i}",
            parameters={"fast_window": 10 if i < 5 else 2, "slow_window": 20 if i < 5 else 8},
        )
        optimizer.observe(scored_candidates=[(candidate, 100.0 if i < 5 else 1.0)])

    suggestions = optimizer.suggest(iteration=11, batch_size=80)
    fast_values = [candidate.parameters["fast_window"] for candidate in suggestions]
    high_count = sum(1 for value in fast_values if value >= 8)

    assert high_count >= 50


def test_determinism() -> None:
    search_space = {"fast_window": (2, 10), "slow_window": (5, 20)}
    a = BayesianOptimizer(search_space=search_space, seed=123)
    b = BayesianOptimizer(search_space=search_space, seed=123)

    observations: list[tuple[Candidate, float]] = []
    for i in range(12):
        params = {"fast_window": 10 - (i % 3), "slow_window": 15 + (i % 5)}
        score = float(i)
        observations.append((Candidate(candidate_id=f"obs-{i}", parameters=params), score))

    a.observe(scored_candidates=observations)
    b.observe(scored_candidates=observations)

    a_out = a.suggest(iteration=12, batch_size=12)
    b_out = b.suggest(iteration=12, batch_size=12)

    assert [candidate.parameters for candidate in a_out] == [candidate.parameters for candidate in b_out]
    assert [candidate.candidate_id for candidate in a_out] == [candidate.candidate_id for candidate in b_out]


def test_checkpoint_restore_roundtrip() -> None:
    search_space = {"fast_window": (2, 10), "slow_window": (5, 20)}
    optimizer = BayesianOptimizer(search_space=search_space, seed=99)

    for i in range(15):
        batch = optimizer.suggest(iteration=i, batch_size=1)
        candidate = batch[0]
        score = float(candidate.parameters["fast_window"] * 10 - candidate.parameters["slow_window"])
        optimizer.observe(scored_candidates=[(candidate, score)])

    state = optimizer.checkpoint()

    restored = BayesianOptimizer(search_space=search_space, seed=99)
    restored.restore(state)

    expected = optimizer.suggest(iteration=16, batch_size=12)
    actual = restored.suggest(iteration=16, batch_size=12)

    assert [candidate.parameters for candidate in actual] == [candidate.parameters for candidate in expected]
    assert [candidate.candidate_id for candidate in actual] == [candidate.candidate_id for candidate in expected]


def test_ordered_pairs_enforced() -> None:
    optimizer = BayesianOptimizer(
        search_space={"fast_window": (2, 10), "slow_window": (5, 20)},
        seed=55,
    )

    suggestions = optimizer.suggest(iteration=0, batch_size=200)

    assert all(
        candidate.parameters["slow_window"] > candidate.parameters["fast_window"] for candidate in suggestions
    )
