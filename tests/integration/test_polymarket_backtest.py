from __future__ import annotations

from math import isfinite
from pathlib import Path

from domains.polymarket.adapter import PolymarketAdapter
from domains.polymarket.data_store import HistoricalMarketStore


SAMPLE_DIR = Path(__file__).resolve().parents[2] / "data" / "polymarket" / "sample"


def test_full_backtest_on_sample_data() -> None:
    store = HistoricalMarketStore(SAMPLE_DIR)
    markets = store.load_all()
    adapter = PolymarketAdapter()

    strategies_with_params = {
        "longshot_fade_v1": {"threshold_low": 45, "threshold_high": 55, "min_confidence": 10},
        "momentum_v1": {"lookback_window": 3, "momentum_threshold": 2, "max_price": 95, "min_price": 5},
        "mean_reversion_v1": {"mean_window": 3, "deviation_threshold": 2, "reversion_strength": 50},
    }

    results = [
        adapter.run(
            markets=markets,
            store=store,
            strategy_id=strategy_id,
            parameters=params,
        )
        for strategy_id, params in strategies_with_params.items()
    ]

    assert any(result.total_bets > 0 for result in results)
    assert all(isfinite(result.roi) for result in results)
    assert all(isfinite(result.final_equity) for result in results)


def test_determinism() -> None:
    store = HistoricalMarketStore(SAMPLE_DIR)
    markets = store.load_all()
    adapter = PolymarketAdapter()
    params = {"threshold_low": 45, "threshold_high": 55, "min_confidence": 10}

    first = adapter.run(
        markets=markets,
        store=store,
        strategy_id="longshot_fade_v1",
        parameters=params,
    )
    second = adapter.run(
        markets=markets,
        store=store,
        strategy_id="longshot_fade_v1",
        parameters=params,
    )

    assert first == second
