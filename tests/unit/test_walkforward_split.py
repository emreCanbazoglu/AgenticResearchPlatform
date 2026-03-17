from __future__ import annotations

from pathlib import Path

import pytest

from domains.trading.adapter import TradingAdapter


def _write_prices(path: Path, prices: list[float]) -> None:
    lines = ["close"] + [str(p) for p in prices]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_trending_prices(n: int, start: float = 100.0, step: float = 1.0) -> list[float]:
    return [start + i * step for i in range(n)]


def test_default_train_ratio_uses_full_series(tmp_path: Path) -> None:
    dataset = tmp_path / "prices.csv"
    prices = _make_trending_prices(60)
    _write_prices(dataset, prices)

    result_default = TradingAdapter().run(
        dataset_id=str(dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 5},
        seed=0,
    )
    result_explicit = TradingAdapter(train_ratio=1.0).run(
        dataset_id=str(dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 5},
        seed=0,
    )

    assert result_default.score == pytest.approx(result_explicit.score)
    assert result_default.metrics["final_equity"] == pytest.approx(
        result_explicit.metrics["final_equity"]
    )


def test_train_ratio_splits_correctly(tmp_path: Path) -> None:
    dataset = tmp_path / "prices.csv"
    prices = _make_trending_prices(100)
    _write_prices(dataset, prices)

    result = TradingAdapter(train_ratio=0.7).run(
        dataset_id=str(dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 5},
        seed=0,
    )

    test_only_dataset = tmp_path / "test_prices.csv"
    train_only_dataset = tmp_path / "train_prices.csv"
    train_prices = prices[:70]  # first 70 rows
    test_prices = prices[70:]  # last 30 rows
    _write_prices(train_only_dataset, train_prices)
    _write_prices(test_only_dataset, test_prices)

    result_train_only = TradingAdapter(train_ratio=1.0).run(
        dataset_id=str(train_only_dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 5},
        seed=0,
    )
    result_test_only = TradingAdapter(train_ratio=1.0).run(
        dataset_id=str(test_only_dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 5},
        seed=0,
    )

    assert result.score == pytest.approx(result_train_only.score)
    assert result.metrics["final_equity"] == pytest.approx(
        result_test_only.metrics["final_equity"]
    )


def test_minimum_split_size_enforced_train(tmp_path: Path) -> None:
    dataset = tmp_path / "prices.csv"
    _write_prices(dataset, _make_trending_prices(20))

    with pytest.raises(ValueError, match="train split"):
        TradingAdapter(train_ratio=0.5).run(
            dataset_id=str(dataset),
            strategy_id="ma_crossover_v1",
            parameters={"fast_window": 2, "slow_window": 5},
            seed=0,
        )


def test_minimum_split_size_enforced_test(tmp_path: Path) -> None:
    dataset = tmp_path / "prices.csv"
    _write_prices(dataset, _make_trending_prices(40))

    with pytest.raises(ValueError, match="test split"):
        TradingAdapter(train_ratio=0.95).run(
            dataset_id=str(dataset),
            strategy_id="ma_crossover_v1",
            parameters={"fast_window": 2, "slow_window": 5},
            seed=0,
        )


def test_metrics_keys_unchanged(tmp_path: Path) -> None:
    dataset = tmp_path / "prices.csv"
    _write_prices(dataset, _make_trending_prices(100))

    result = TradingAdapter(train_ratio=0.7).run(
        dataset_id=str(dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 5},
        seed=0,
    )

    expected_keys = {
        "initial_equity",
        "final_equity",
        "total_return",
        "trade_count",
        "commission_paid",
        "slippage_paid",
        "max_drawdown",
        "annualized_volatility",
        "sharpe_ratio",
        "win_rate",
    }
    assert set(result.metrics.keys()) == expected_keys
