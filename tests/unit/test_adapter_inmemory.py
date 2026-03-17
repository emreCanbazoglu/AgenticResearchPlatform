from __future__ import annotations

from pathlib import Path

import pytest

from domains.trading.adapter import STRATEGY_REGISTRY, TradingAdapter
from scoring.metrics import profitability_score


def _write_close_only_csv(path: Path, closes: list[float]) -> None:
    lines = ["close"] + [str(price) for price in closes]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_prices(count: int = 100) -> list[float]:
    return [100.0 + ((i % 10) - 5) * 1.5 + (i * 0.1) for i in range(count)]


def test_run_on_prices_matches_run_with_full_dataset(tmp_path: Path) -> None:
    prices = _make_prices(120)
    dataset = tmp_path / "prices.csv"
    _write_close_only_csv(dataset, prices)

    adapter = TradingAdapter(train_ratio=1.0)
    run_result = adapter.run(
        dataset_id=str(dataset),
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 3, "slow_window": 8},
        seed=42,
    )
    inmem_result = adapter.run_on_prices(
        prices=prices,
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 3, "slow_window": 8},
        seed=42,
    )

    assert inmem_result.metrics == run_result.metrics
    assert inmem_result.score == run_result.score


def test_run_on_prices_rejects_short_list() -> None:
    adapter = TradingAdapter()

    with pytest.raises(ValueError, match="prices list needs at least 20 rows"):
        adapter.run_on_prices(
            prices=[100.0] * 19,
            strategy_id="ma_crossover_v1",
            parameters={"fast_window": 2, "slow_window": 3},
            seed=0,
        )


def test_run_on_prices_does_not_split() -> None:
    prices = _make_prices(100)
    adapter = TradingAdapter(initial_capital=12_500.0, commission_rate=0.002, train_ratio=0.5)
    parameters = {"fast_window": 3, "slow_window": 9}

    result = adapter.run_on_prices(
        prices=prices,
        strategy_id="ma_crossover_v1",
        parameters=parameters,
        seed=1,
    )

    runner = STRATEGY_REGISTRY["ma_crossover_v1"]
    strategy_parameters = {
        "_initial_capital": adapter.initial_capital,
        "commission_rate": adapter.commission_rate,
        **parameters,
    }
    (
        final_equity,
        trade_count,
        _equity_curve,
        _trade_pnls,
        _commission_paid,
        _slippage_paid,
    ) = runner(prices, strategy_parameters)

    assert result.metrics["trade_count"] == float(trade_count)
    assert result.metrics["final_equity"] == pytest.approx(final_equity)
    assert result.metrics["total_return"] == pytest.approx(
        profitability_score(adapter.initial_capital, final_equity)
    )


def test_run_and_run_on_prices_share_same_logic(tmp_path: Path) -> None:
    prices = _make_prices(100)
    dataset = tmp_path / "prices.csv"
    _write_close_only_csv(dataset, prices)
    adapter = TradingAdapter(train_ratio=1.0)
    parameters = {"fast_window": 4, "slow_window": 10}

    run_result = adapter.run(
        dataset_id=str(dataset),
        strategy_id="ma_crossover_v1",
        parameters=parameters,
        seed=7,
    )
    inmem_result = adapter.run_on_prices(
        prices=prices,
        strategy_id="ma_crossover_v1",
        parameters=parameters,
        seed=7,
    )

    assert run_result.metrics == inmem_result.metrics
