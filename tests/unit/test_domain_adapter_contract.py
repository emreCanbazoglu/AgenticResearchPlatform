from __future__ import annotations

import pytest

from core.execution.adapters import get_adapter
from domains.game_economy.adapter import GameEconomyAdapter
from domains.trading.adapter import TradingAdapter


def test_adapter_registry_returns_expected_types() -> None:
    assert isinstance(get_adapter("trading"), TradingAdapter)
    assert isinstance(get_adapter("game_economy"), GameEconomyAdapter)


def test_adapter_registry_rejects_unknown_domain() -> None:
    with pytest.raises(ValueError, match="unsupported domain"):
        get_adapter("unknown")
