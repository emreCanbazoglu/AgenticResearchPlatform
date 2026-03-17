from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.multi_agent.director import CycleSummary, Director
from core.multi_agent.worker_agent import CycleResult, WorkerAgent

_BASE_URL = "https://api.binance.com/api/v3/klines"


@dataclass
class PaperSessionConfig:
    symbol: str = "BTCUSDT"
    interval: str = "30m"
    cycle_size: int = 48
    lookback_size: int = 200
    n_tune_candidates: int = 8
    checkpoint_path: str = "paper_session.json"
    total_budget: float = 30_000.0


def fetch_candles(symbol: str, interval: str, limit: int) -> list[float]:
    url = f"{_BASE_URL}?symbol={symbol}&interval={interval}&limit={limit}"

    try:
        with urllib.request.urlopen(url) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise RuntimeError(f"failed to fetch candles for {symbol}: HTTP {status}")
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"failed to fetch candles for {symbol}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to fetch candles for {symbol}: network error ({exc.reason})") from exc

    try:
        rows = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"failed to fetch candles for {symbol}: malformed JSON response") from exc

    if not isinstance(rows, list):
        raise RuntimeError(f"failed to fetch candles for {symbol}: malformed payload")

    closes: list[float] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, list) or len(row) <= 4:
            raise RuntimeError(f"failed to fetch candles for {symbol}: malformed row at index {idx}")
        try:
            closes.append(float(row[4]))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"failed to fetch candles for {symbol}: invalid close value at index {idx}"
            ) from exc

    return closes


class PaperSession:
    def __init__(self, config: PaperSessionConfig, workers: list[WorkerAgent]) -> None:
        self.config = config
        self.workers = workers
        self.director = Director(total_budget=config.total_budget, workers=workers)
        self._history: list[CycleSummary] = []
        self._cycle_count = 0

    def run_one_cycle(self) -> CycleSummary:
        fetch_limit = self.config.lookback_size + self.config.cycle_size
        all_candles = fetch_candles(
            symbol=self.config.symbol,
            interval=self.config.interval,
            limit=fetch_limit,
        )

        tune_prices = all_candles[: self.config.lookback_size]
        # Eval on the full window so strategies can warm up their indicators
        # (e.g. a slow_window=47 MA needs 47 bars before it can fire).
        # cycle_size controls how much the window slides forward each cycle,
        # not how many bars the backtest sees.
        eval_prices = all_candles

        for worker in self.workers:
            worker.self_tune(tune_prices, self.config.n_tune_candidates)

        allocations = self.director._allocate()
        total_before = self.director.total_budget

        results = [
            worker.run_eval(eval_prices, allocations[worker.strategy_id], self._cycle_count)
            for worker in self.workers
        ]

        real_pnl = 0.0
        for result in results:
            if not result.is_virtual:
                real_pnl += result.pnl
                self.director._cumulative_real_pnl[result.strategy_id] += result.pnl

        self.director.total_budget += real_pnl

        for result in results:
            self.director._observe(result.strategy_id, result.pnl_pct)

        self.director._completed_cycles += 1

        cycle_summary = CycleSummary(
            cycle_idx=self._cycle_count,
            total_budget_before=total_before,
            total_budget_after=self.director.total_budget,
            allocations=allocations,
            results=results,
        )
        self._history.append(cycle_summary)
        self._cycle_count += 1
        return cycle_summary

    def save(self, path: str | None = None) -> None:
        target = Path(path or self.config.checkpoint_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_suffix(f"{target.suffix}.tmp")

        payload = {
            "config": asdict(self.config),
            "cycle_count": self._cycle_count,
            "total_budget": self.director.total_budget,
            "workers": [worker.checkpoint() for worker in self.workers],
            "history": [self._cycle_summary_to_dict(summary) for summary in self._history],
            "director": {
                "obs_count": self.director.obs_count,
                "sum_pnl_pct": self.director.sum_pnl_pct,
                "cumulative_real_pnl": self.director._cumulative_real_pnl,
                "completed_cycles": self.director._completed_cycles,
            },
        }

        serialized = json.dumps(payload, indent=2)
        tmp_target.write_text(serialized, encoding="utf-8")
        os.replace(str(tmp_target), str(target))

    @classmethod
    def load(cls, path: str, workers: list[WorkerAgent]) -> PaperSession:
        checkpoint_path = Path(path)
        if not checkpoint_path.exists():
            return cls(PaperSessionConfig(checkpoint_path=path), workers)

        try:
            raw_payload = checkpoint_path.read_text(encoding="utf-8")
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"corrupt checkpoint: {path}") from exc

        config = PaperSessionConfig(**payload.get("config", {}))
        config.checkpoint_path = path
        session = cls(config, workers)

        session._cycle_count = int(payload.get("cycle_count", 0))
        session.director.total_budget = float(payload.get("total_budget", config.total_budget))

        states_by_strategy = {
            str(state.get("strategy_id", "")): state for state in payload.get("workers", [])
        }
        for worker in session.workers:
            worker_state = states_by_strategy.get(worker.strategy_id)
            if worker_state is not None:
                worker.restore(worker_state)

        session._history = [
            cls._cycle_summary_from_dict(item) for item in payload.get("history", [])
        ]

        director_state = payload.get("director", {})
        if isinstance(director_state, dict):
            session.director.obs_count = {
                str(key): int(value) for key, value in director_state.get("obs_count", {}).items()
            }
            session.director.sum_pnl_pct = {
                str(key): float(value)
                for key, value in director_state.get("sum_pnl_pct", {}).items()
            }
            session.director._cumulative_real_pnl = {
                str(key): float(value)
                for key, value in director_state.get("cumulative_real_pnl", {}).items()
            }
            session.director._completed_cycles = int(
                director_state.get("completed_cycles", session._cycle_count)
            )

        return session

    def summary(self) -> dict[str, Any]:
        if self._history:
            initial_budget = self._history[0].total_budget_before
        else:
            initial_budget = self.config.total_budget

        current_budget = self.director.total_budget
        total_return_pct = 0.0
        if initial_budget != 0:
            total_return_pct = (current_budget - initial_budget) / initial_budget

        cumulative_pnl_pct: dict[str, float] = {}
        for cycle in self._history:
            for result in cycle.results:
                cumulative_pnl_pct[result.strategy_id] = (
                    cumulative_pnl_pct.get(result.strategy_id, 0.0) + result.pnl_pct
                )

        if cumulative_pnl_pct:
            best_worker = max(sorted(cumulative_pnl_pct), key=lambda sid: cumulative_pnl_pct[sid])
        else:
            best_worker = ""

        return {
            "cycle_count": self._cycle_count,
            "initial_budget": float(initial_budget),
            "current_budget": float(current_budget),
            "total_return_pct": float(total_return_pct),
            "best_worker": best_worker,
            "history_len": len(self._history),
        }

    @staticmethod
    def _cycle_summary_to_dict(summary: CycleSummary) -> dict[str, Any]:
        return {
            "cycle_idx": summary.cycle_idx,
            "total_budget_before": summary.total_budget_before,
            "total_budget_after": summary.total_budget_after,
            "allocations": dict(summary.allocations),
            "results": [asdict(result) for result in summary.results],
        }

    @staticmethod
    def _cycle_summary_from_dict(payload: dict[str, Any]) -> CycleSummary:
        results = [CycleResult(**result_payload) for result_payload in payload.get("results", [])]
        return CycleSummary(
            cycle_idx=int(payload.get("cycle_idx", 0)),
            total_budget_before=float(payload.get("total_budget_before", 0.0)),
            total_budget_after=float(payload.get("total_budget_after", 0.0)),
            allocations={
                str(key): float(value)
                for key, value in payload.get("allocations", {}).items()
            },
            results=results,
        )
