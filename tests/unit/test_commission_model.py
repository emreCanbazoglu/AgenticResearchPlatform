from __future__ import annotations

from pathlib import Path

import pytest

from domains.trading.adapter import TradingAdapter


def _write_close_only_csv(path: Path, closes: list[float]) -> None:
    lines = ["close"] + [str(price) for price in closes]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_commission_is_deducted_on_buy_and_sell(tmp_path: Path) -> None:
    dataset = tmp_path / "prices.csv"
    closes = [10.0, 10.0, 10.0, 12.0, 8.0] + [8.0] * 15
    _write_close_only_csv(dataset, closes)

    result = TradingAdapter(initial_capital=10_000.0).run(
        dataset_id=str(dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 3, "commission_rate": 0.001},
        seed=0,
    )

    assert result.metrics["trade_count"] == 2.0
    assert result.metrics["commission_paid"] == pytest.approx(16.66)
    assert result.metrics["final_equity"] == pytest.approx(6653.34)


def test_commission_rate_zero_matches_baseline_no_commission(tmp_path: Path) -> None:
    dataset = tmp_path / "prices.csv"
    closes = [10.0, 10.0, 10.0, 12.0, 8.0] + [8.0] * 15
    _write_close_only_csv(dataset, closes)

    baseline = TradingAdapter(initial_capital=10_000.0, commission_rate=0.0).run(
        dataset_id=str(dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 3},
        seed=0,
    )

    override_zero = TradingAdapter(initial_capital=10_000.0, commission_rate=0.001).run(
        dataset_id=str(dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 3, "commission_rate": 0.0},
        seed=0,
    )

    assert override_zero.metrics["final_equity"] == pytest.approx(baseline.metrics["final_equity"])
    assert override_zero.metrics["total_return"] == pytest.approx(baseline.metrics["total_return"])
    assert override_zero.metrics["commission_paid"] == pytest.approx(0.0)


def test_no_trades_have_zero_commission_paid(tmp_path: Path) -> None:
    dataset = tmp_path / "prices.csv"
    closes = [10.0] * 20
    _write_close_only_csv(dataset, closes)

    result = TradingAdapter().run(
        dataset_id=str(dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 3},
        seed=0,
    )

    assert "commission_paid" in result.metrics
    assert result.metrics["trade_count"] == 0.0
    assert result.metrics["commission_paid"] == pytest.approx(0.0)
