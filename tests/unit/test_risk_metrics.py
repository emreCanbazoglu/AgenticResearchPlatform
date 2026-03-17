from __future__ import annotations

import math

from scoring.metrics import (
    DEFAULT_WEIGHTS,
    annualized_volatility,
    composite_score,
    load_scoring_weights,
    max_drawdown,
    sharpe_ratio,
    win_rate,
)


def test_max_drawdown_flat_curve_is_zero() -> None:
    assert max_drawdown([10000, 10000]) == 0.0


def test_max_drawdown_peak_to_trough() -> None:
    assert max_drawdown([10000, 8000, 9000]) == 0.2


def test_annualized_volatility_returns_zero_for_short_series() -> None:
    assert annualized_volatility([0.01]) == 0.0


def test_sharpe_ratio_positive_for_consistent_positive_returns() -> None:
    assert sharpe_ratio([0.01] * 10) > 0.0


def test_sharpe_ratio_zero_for_flat_zero_returns() -> None:
    assert sharpe_ratio([0.0] * 10) == 0.0


def test_win_rate_empty_is_zero() -> None:
    assert win_rate([]) == 0.0


def test_win_rate_mixed_trades() -> None:
    assert math.isclose(win_rate([10.0, -5.0, 2.0, 0.0]), 0.5)


def test_composite_score_uses_expected_formula() -> None:
    metrics = {"total_return": 0.2, "sharpe_ratio": 1.1, "max_drawdown": 0.1}
    weights = {"return": 0.4, "sharpe": 0.4, "drawdown": 0.2}
    expected = (0.4 * 0.2) + (0.4 * 1.1) - (0.2 * 0.1)
    assert math.isclose(composite_score(metrics, weights), expected)


def test_load_scoring_weights_reads_file(tmp_path) -> None:
    config_path = tmp_path / "scoring.yaml"
    config_path.write_text(
        "return_weight: 0.5\nsharpe_weight: 0.3\ndrawdown_weight: 0.2\n",
        encoding="utf-8",
    )

    weights = load_scoring_weights(str(config_path))
    assert weights == {
        "return_weight": 0.5,
        "sharpe_weight": 0.3,
        "drawdown_weight": 0.2,
    }


def test_load_scoring_weights_missing_file_returns_defaults(tmp_path) -> None:
    missing_path = tmp_path / "nonexistent.yaml"
    assert load_scoring_weights(str(missing_path)) == DEFAULT_WEIGHTS
