from __future__ import annotations

import pytest

from domains.trading.adapter import TradingAdapter, _run_backtest


class _BuyThenSellStrategy:
    def signal(self, prices: list[float], idx: int) -> int:
        if idx == 0:
            return 1
        if idx == 1:
            return -1
        return 0


def _make_prices(count: int = 200) -> list[float]:
    return [100.0 + (i * 0.2) + (((i % 20) - 10) * 1.5) for i in range(count)]


def test_default_params_match_old_behaviour() -> None:
    prices = [10.0, 10.0, 10.0, 12.0, 8.0] + [8.0] * 15

    result = TradingAdapter(initial_capital=10_000.0).run_on_prices(
        prices=prices,
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 2, "slow_window": 3},
        seed=0,
    )

    assert result.metrics["trade_count"] == 2.0
    assert result.metrics["commission_paid"] == pytest.approx(16.66)
    assert result.metrics["final_equity"] == pytest.approx(6653.34)


def test_position_size_fraction_limits_investment() -> None:
    final_equity, trade_count, _equity_curve, trade_pnls, _commission_paid, _slippage_paid = _run_backtest(
        prices=[10.0, 20.0, 20.0],
        strategy=_BuyThenSellStrategy(),
        initial_capital=10_000.0,
        commission_rate=0.0,
        position_size_fraction=0.5,
        slippage_rate=0.0,
    )

    assert trade_count == 2
    assert final_equity == pytest.approx(15_000.0)
    assert trade_pnls == pytest.approx([5_000.0])


def test_slippage_reduces_pnl() -> None:
    prices = _make_prices()
    params = {"fast_window": 3, "slow_window": 8}

    no_slippage = TradingAdapter(slippage_rate=0.0).run_on_prices(
        prices=prices,
        strategy_id="ma_crossover_v1",
        parameters=params,
        seed=0,
    )
    with_slippage = TradingAdapter(slippage_rate=0.01).run_on_prices(
        prices=prices,
        strategy_id="ma_crossover_v1",
        parameters=params,
        seed=0,
    )

    assert with_slippage.metrics["final_equity"] < no_slippage.metrics["final_equity"]


def test_slippage_paid_in_metrics() -> None:
    prices = _make_prices()
    result = TradingAdapter(slippage_rate=0.001).run_on_prices(
        prices=prices,
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 3, "slow_window": 8},
        seed=0,
    )

    assert result.metrics["trade_count"] > 0
    assert result.metrics["slippage_paid"] > 0.0


def test_slippage_zero_by_default() -> None:
    prices = _make_prices()
    result = TradingAdapter().run_on_prices(
        prices=prices,
        strategy_id="ma_crossover_v1",
        parameters={"fast_window": 3, "slow_window": 8},
        seed=0,
    )

    assert result.metrics["slippage_paid"] == pytest.approx(0.0)


def test_fraction_one_slippage_zero_is_backward_compatible() -> None:
    prices = _make_prices()
    strategy_parameters = {
        "ma_crossover_v1": {"fast_window": 3, "slow_window": 8},
        "rsi_v1": {"period": 14, "overbought": 70.0, "oversold": 30.0},
        "macd_v1": {"fast_period": 6, "slow_period": 20, "signal_period": 7},
    }

    for strategy_id, params in strategy_parameters.items():
        baseline = TradingAdapter().run_on_prices(
            prices=prices,
            strategy_id=strategy_id,
            parameters=params,
            seed=0,
        )
        explicit_defaults = TradingAdapter().run_on_prices(
            prices=prices,
            strategy_id=strategy_id,
            parameters={
                **params,
                "position_size_fraction": 1.0,
                "slippage_rate": 0.0,
            },
            seed=0,
        )

        assert explicit_defaults.metrics["final_equity"] == pytest.approx(
            baseline.metrics["final_equity"]
        )
        assert explicit_defaults.metrics["total_return"] == pytest.approx(
            baseline.metrics["total_return"]
        )
        assert explicit_defaults.metrics["trade_count"] == baseline.metrics["trade_count"]
        assert explicit_defaults.metrics["commission_paid"] == pytest.approx(
            baseline.metrics["commission_paid"]
        )
        assert explicit_defaults.metrics["slippage_paid"] == pytest.approx(
            baseline.metrics["slippage_paid"]
        )
