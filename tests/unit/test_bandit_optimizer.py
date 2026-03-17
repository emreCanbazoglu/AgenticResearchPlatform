from __future__ import annotations

from meta.optimizers.bandit import BanditOptimizer
from meta.optimizers.base import Candidate


def _score_from_id(candidate: Candidate) -> float:
    return float(int(candidate.candidate_id.split("-")[1]))


def test_pool_initialized_with_correct_size() -> None:
    optimizer = BanditOptimizer(
        search_space={"x": (0, 10)},
        seed=7,
        pool_size=20,
    )

    seen_ids: set[str] = set()
    for iteration in range(30):
        suggested = optimizer.suggest(iteration=iteration, batch_size=5)
        seen_ids.update(candidate.candidate_id for candidate in suggested)
        optimizer.observe(scored_candidates=[(candidate, 0.0) for candidate in suggested])

    assert len(seen_ids) <= 20


def test_untried_arms_selected_first() -> None:
    optimizer = BanditOptimizer(
        search_space={"x": (0, 10)},
        seed=11,
        pool_size=10,
    )

    first = optimizer.suggest(iteration=0, batch_size=3)
    optimizer.observe(scored_candidates=[(candidate, 0.0) for candidate in first])
    second = optimizer.suggest(iteration=1, batch_size=3)

    first_ids = {candidate.candidate_id for candidate in first}
    second_ids = {candidate.candidate_id for candidate in second}

    assert first_ids.isdisjoint(second_ids)


def test_ucb_exploits_after_observations() -> None:
    optimizer = BanditOptimizer(
        search_space={"x": (0, 10)},
        seed=42,
        pool_size=6,
        exploration_coeff=1.0,
    )

    # Explore all arms once.
    for iteration in range(3):
        batch = optimizer.suggest(iteration=iteration, batch_size=2)
        optimizer.observe(scored_candidates=[(candidate, 0.0) for candidate in batch])

    target = optimizer.suggest(iteration=3, batch_size=1)[0]

    # Make one arm clearly superior.
    for _ in range(5):
        optimizer.observe(scored_candidates=[(target, 50.0)])

    follow_up = optimizer.suggest(iteration=4, batch_size=3)
    follow_up_ids = {candidate.candidate_id for candidate in follow_up}

    assert target.candidate_id in follow_up_ids


def test_determinism() -> None:
    kwargs = {
        "search_space": {"fast_window": (2, 8), "slow_window": (9, 20)},
        "seed": 123,
        "pool_size": 12,
        "exploration_coeff": 1.0,
    }
    optimizer_a = BanditOptimizer(**kwargs)
    optimizer_b = BanditOptimizer(**kwargs)

    assert optimizer_a.checkpoint()["pool"] == optimizer_b.checkpoint()["pool"]

    first_a = optimizer_a.suggest(iteration=0, batch_size=4)
    first_b = optimizer_b.suggest(iteration=0, batch_size=4)

    assert [c.candidate_id for c in first_a] == [c.candidate_id for c in first_b]

    observations_a = [(candidate, _score_from_id(candidate)) for candidate in first_a]
    observations_b = [(candidate, _score_from_id(candidate)) for candidate in first_b]
    optimizer_a.observe(scored_candidates=observations_a)
    optimizer_b.observe(scored_candidates=observations_b)

    second_a = optimizer_a.suggest(iteration=1, batch_size=4)
    second_b = optimizer_b.suggest(iteration=1, batch_size=4)

    assert [c.candidate_id for c in second_a] == [c.candidate_id for c in second_b]


def test_checkpoint_restore_roundtrip() -> None:
    optimizer = BanditOptimizer(
        search_space={"x": (0, 10), "y": (0, 10)},
        seed=55,
        pool_size=16,
    )

    for iteration in range(5):
        batch = optimizer.suggest(iteration=iteration, batch_size=4)
        optimizer.observe(
            scored_candidates=[(candidate, float(iteration) + _score_from_id(candidate)) for candidate in batch]
        )

    checkpoint = optimizer.checkpoint()

    restored = BanditOptimizer(
        search_space={"x": (0, 10), "y": (0, 10)},
        seed=999,
        pool_size=4,
    )
    restored.restore(checkpoint)

    next_original = optimizer.suggest(iteration=5, batch_size=4)
    next_restored = restored.suggest(iteration=5, batch_size=4)

    assert [c.candidate_id for c in next_original] == [c.candidate_id for c in next_restored]


def test_ordered_pairs_enforced_in_pool() -> None:
    optimizer = BanditOptimizer(
        search_space={"fast_window": (2, 8), "slow_window": (3, 20)},
        seed=2024,
        pool_size=100,
    )

    for item in optimizer.checkpoint()["pool"]:
        params = item["parameters"]
        assert params["slow_window"] > params["fast_window"]


def test_suggest_returns_exact_batch_size() -> None:
    optimizer = BanditOptimizer(
        search_space={"x": (0, 10)},
        seed=5,
        pool_size=10,
    )

    suggested = optimizer.suggest(iteration=0, batch_size=5)

    assert len(suggested) == 5
