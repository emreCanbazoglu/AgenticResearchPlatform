from __future__ import annotations

from domains.base import DomainRunResult, EnvironmentAdapter
from domains.game_economy.adapter import GameEconomyAdapter
from domains.polymarket.adapter import PolymarketAdapter
from domains.trading.adapter import TradingAdapter


class _PolymarketExecutionAdapter:
    def __init__(self) -> None:
        self._adapter = PolymarketAdapter()

    def run(
        self,
        *,
        dataset_id: str,
        strategy_id: str,
        parameters: dict[str, float],
        seed: int,
    ) -> DomainRunResult:
        return self._adapter.run_for_execution(
            dataset_id=dataset_id,
            strategy_id=strategy_id,
            parameters=parameters,
            seed=seed,
        )


def get_adapter(domain: str) -> EnvironmentAdapter:
    if domain == "trading":
        return TradingAdapter()
    if domain == "polymarket":
        return _PolymarketExecutionAdapter()
    if domain == "game_economy":
        return GameEconomyAdapter()
    raise ValueError(f"unsupported domain: {domain}")
