from __future__ import annotations

import pytest

from domains.trading.adapter import TradingAdapter
from domains.trading.strategies.macd import MACDStrategy
from domains.trading.strategies.rsi import RSIStrategy


def test_rsi_overbought_on_monotonic_increase() -> None:
    prices = [float(i) for i in range(1, 60)]
    strategy = RSIStrategy(period=14, overbought=70.0, oversold=30.0)

    assert strategy.signal(prices, 14) == -1


def test_rsi_oversold_on_monotonic_decrease() -> None:
    prices = [float(100 - i) for i in range(60)]
    strategy = RSIStrategy(period=14, overbought=70.0, oversold=30.0)

    assert strategy.signal(prices, 14) == 1


def test_macd_returns_zero_with_insufficient_history() -> None:
    prices = [float(i) for i in range(1, 80)]
    strategy = MACDStrategy(fast_period=12, slow_period=26, signal_period=9)

    assert strategy.signal(prices, 34) == 0


def test_macd_fast_slow_validation() -> None:
    adapter = TradingAdapter()

    with pytest.raises(ValueError, match="fast_period must be < slow_period"):
        adapter.run(
            dataset_id="data/trading/sample_ohlcv.csv",
            strategy_id="macd_v1",
            parameters={"fast_period": 26, "slow_period": 26, "signal_period": 9},
            seed=0,
        )
