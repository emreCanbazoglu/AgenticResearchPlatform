from __future__ import annotations

from domains.base import EnvironmentAdapter
from domains.game_economy.adapter import GameEconomyAdapter
from domains.trading.adapter import TradingAdapter


def get_adapter(domain: str) -> EnvironmentAdapter:
    if domain == "trading":
        return TradingAdapter()
    if domain == "game_economy":
        return GameEconomyAdapter()
    raise ValueError(f"unsupported domain: {domain}")
