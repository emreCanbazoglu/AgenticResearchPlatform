from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from domains.polymarket.data_store import HistoricalMarketStore


SAMPLE_DIR = Path(__file__).resolve().parents[2] / "data" / "polymarket" / "sample"


def test_load_all_returns_sorted_by_resolution_date() -> None:
    store = HistoricalMarketStore(SAMPLE_DIR)

    markets = store.load_all()

    resolved_times = [market.resolved_at for market in markets]
    assert resolved_times == sorted(resolved_times)


def test_get_price_series_returns_sorted_ascending() -> None:
    store = HistoricalMarketStore(SAMPLE_DIR)

    series = store.get_price_series("mkt001")

    timestamps = [point.timestamp for point in series]
    assert timestamps == sorted(timestamps)


def test_get_by_category_filters_correctly() -> None:
    store = HistoricalMarketStore(SAMPLE_DIR)

    markets = store.get_by_category("sports")

    assert markets
    assert all(market.category == "sports" for market in markets)


def test_get_resolved_before_excludes_later_markets() -> None:
    store = HistoricalMarketStore(SAMPLE_DIR)
    cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)

    markets = store.get_resolved_before(cutoff)

    assert markets
    assert all(market.resolved_at < cutoff for market in markets)


def test_empty_price_series_handled() -> None:
    store = HistoricalMarketStore(SAMPLE_DIR)

    series = store.get_price_series("market-does-not-exist")

    assert series == []


def test_market_record_fields_parsed() -> None:
    store = HistoricalMarketStore(SAMPLE_DIR)

    market = store.load_all()[0]

    assert isinstance(market.outcome, float)
    assert isinstance(market.created_at, datetime)
    assert isinstance(market.resolved_at, datetime)
    assert isinstance(market.tags, list)
    assert all(isinstance(tag, str) for tag in market.tags)
