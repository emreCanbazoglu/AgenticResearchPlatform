from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.multi_agent.director import CycleSummary
from core.multi_agent.worker_agent import CycleResult, WorkerAgent
from domains.polymarket.adapter import BetRecord, kelly_fraction
from domains.polymarket.base import BetAction, BetDecision, MarketSnapshot


@dataclass
class PolymarketPaperConfig:
    categories: list[str] = field(default_factory=lambda: ["elections", "crypto", "sports"])
    max_open_markets: int = 50
    cycle_interval_hours: int = 24
    initial_capital: float = 10_000.0
    max_kelly_fraction: float = 0.25
    checkpoint_path: str = "paper_polymarket.json"
    use_llm: bool = False


@dataclass
class VirtualPosition:
    market_id: str
    question: str
    action: BetAction
    entry_price: float
    bet_amount: float
    shares: float
    opened_at: datetime
    estimated_prob: float
    strategy_id: str


@dataclass
class VirtualPortfolio:
    cash: float
    open_positions: list[VirtualPosition]
    closed_positions: list[BetRecord]
    total_profit: float


class PolymarketPaperSession:
    _BASE_URL = "https://clob.polymarket.com"
    _MIN_REQUEST_INTERVAL_SECONDS = 0.1  # 10 req/s max

    def __init__(
        self,
        config: PolymarketPaperConfig,
        workers: list[WorkerAgent],
        *,
        dry_run: bool = False,
    ) -> None:
        self.config = config
        self.workers = workers
        self.dry_run = bool(dry_run)

        self.portfolio = VirtualPortfolio(
            cash=float(config.initial_capital),
            open_positions=[],
            closed_positions=[],
            total_profit=0.0,
        )

        self._cycle_count = 0
        self._history: list[CycleSummary] = []
        self._last_request_ts: float | None = None

        self._obs_count: dict[str, int] = {worker.strategy_id: 0 for worker in workers}
        self._sum_pnl_pct: dict[str, float] = {worker.strategy_id: 0.0 for worker in workers}
        self._completed_cycles = 0

    def run_one_cycle(self) -> CycleSummary:
        total_before = self._portfolio_value()

        open_snapshots, categories_by_market = self._fetch_open_market_snapshots()
        resolved_by_worker = self._resolve_open_positions(categories_by_market)

        self._tune_workers(resolved_by_worker)

        allocations = self._allocate_budget(self.portfolio.cash)
        decisions = self._evaluate_open_markets(open_snapshots)
        placed_by_worker = self._place_virtual_bets(decisions, allocations)

        results = self._build_cycle_results(allocations, resolved_by_worker, placed_by_worker)

        for result in results:
            self._observe_worker(result.strategy_id, result.pnl_pct)

        self._completed_cycles += 1
        total_after = self._portfolio_value(
            current_prices={snapshot.market_id: snapshot.current_price for snapshot in open_snapshots}
        )

        cycle_summary = CycleSummary(
            cycle_idx=self._cycle_count,
            total_budget_before=total_before,
            total_budget_after=total_after,
            allocations=allocations,
            results=results,
        )
        self._history.append(cycle_summary)
        self._cycle_count += 1

        if not self.dry_run:
            self.save()

        return cycle_summary

    def save(self, path: str | None = None) -> None:
        target = Path(path or self.config.checkpoint_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_suffix(f"{target.suffix}.tmp")

        payload = {
            "config": asdict(self.config),
            "dry_run": self.dry_run,
            "cycle_count": self._cycle_count,
            "portfolio": {
                "cash": self.portfolio.cash,
                "total_profit": self.portfolio.total_profit,
                "open_positions": [self._virtual_position_to_dict(pos) for pos in self.portfolio.open_positions],
                "closed_positions": [self._bet_record_to_dict(record) for record in self.portfolio.closed_positions],
            },
            "history": [self._cycle_summary_to_dict(summary) for summary in self._history],
            "workers": [worker.checkpoint() for worker in self.workers if hasattr(worker, "checkpoint")],
            "ucb": {
                "obs_count": self._obs_count,
                "sum_pnl_pct": self._sum_pnl_pct,
                "completed_cycles": self._completed_cycles,
            },
        }

        serialized = json.dumps(payload, indent=2)
        tmp_target.write_text(serialized, encoding="utf-8")
        os.replace(str(tmp_target), str(target))

    @classmethod
    def load(cls, path: str, workers: list[WorkerAgent]) -> PolymarketPaperSession:
        checkpoint_path = Path(path)
        if not checkpoint_path.exists():
            return cls(PolymarketPaperConfig(checkpoint_path=path), workers)

        try:
            payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"corrupt checkpoint: {path}") from exc

        config = PolymarketPaperConfig(**payload.get("config", {}))
        config.checkpoint_path = path
        session = cls(config, workers, dry_run=bool(payload.get("dry_run", False)))

        session._cycle_count = int(payload.get("cycle_count", 0))

        portfolio_payload = payload.get("portfolio", {})
        if isinstance(portfolio_payload, dict):
            session.portfolio.cash = float(portfolio_payload.get("cash", config.initial_capital))
            session.portfolio.total_profit = float(portfolio_payload.get("total_profit", 0.0))
            session.portfolio.open_positions = [
                cls._virtual_position_from_dict(item)
                for item in portfolio_payload.get("open_positions", [])
                if isinstance(item, dict)
            ]
            session.portfolio.closed_positions = [
                cls._bet_record_from_dict(item)
                for item in portfolio_payload.get("closed_positions", [])
                if isinstance(item, dict)
            ]

        session._history = [
            cls._cycle_summary_from_dict(item)
            for item in payload.get("history", [])
            if isinstance(item, dict)
        ]

        worker_states = {
            str(state.get("strategy_id", "")): state
            for state in payload.get("workers", [])
            if isinstance(state, dict)
        }
        for worker in session.workers:
            state = worker_states.get(worker.strategy_id)
            if state is not None and hasattr(worker, "restore"):
                worker.restore(state)

        ucb = payload.get("ucb", {})
        if isinstance(ucb, dict):
            session._obs_count = {
                str(key): int(value)
                for key, value in ucb.get("obs_count", session._obs_count).items()
            }
            session._sum_pnl_pct = {
                str(key): float(value)
                for key, value in ucb.get("sum_pnl_pct", session._sum_pnl_pct).items()
            }
            session._completed_cycles = int(ucb.get("completed_cycles", session._cycle_count))

        return session

    def summary(self) -> dict[str, Any]:
        portfolio_value = self._portfolio_value()
        roi = 0.0
        if self.config.initial_capital != 0:
            roi = (portfolio_value - self.config.initial_capital) / self.config.initial_capital

        return {
            "cycle_count": self._cycle_count,
            "cash": float(self.portfolio.cash),
            "open_positions": len(self.portfolio.open_positions),
            "closed_positions": len(self.portfolio.closed_positions),
            "total_profit": float(self.portfolio.total_profit),
            "portfolio_value": float(portfolio_value),
            "roi": float(roi),
            "dry_run": self.dry_run,
        }

    def _fetch_open_market_snapshots(self) -> tuple[list[MarketSnapshot], dict[str, str]]:
        payload = self._get_json(
            "/markets",
            {
                "active": "true",
                "limit": self.config.max_open_markets,
            },
        )
        raw_markets = self._extract_market_list(payload)

        categories = {value.lower() for value in self.config.categories}
        snapshots: list[MarketSnapshot] = []
        categories_by_market: dict[str, str] = {}

        for raw in raw_markets:
            market_id = self._market_id(raw)
            if not market_id:
                continue

            category = str(raw.get("category") or "").strip().lower()
            if categories and category not in categories:
                continue

            history_payload = self._get_json(
                "/prices-history",
                {
                    "market": market_id,
                    "interval": "1h",
                },
            )
            price_history = self._extract_price_history(history_payload)
            if not price_history:
                fallback_price = self._extract_market_price(raw)
                if fallback_price is None:
                    continue
                price_history = [fallback_price]

            current_price = price_history[-1]
            if not (0.0 < current_price < 1.0):
                continue

            snapshot = MarketSnapshot(
                market_id=market_id,
                question=str(raw.get("question") or raw.get("title") or ""),
                category=category or "unknown",
                current_price=current_price,
                price_history=price_history,
                days_to_resolution=self._days_to_resolution(raw),
                tags=self._extract_tags(raw),
            )
            snapshots.append(snapshot)
            categories_by_market[market_id] = snapshot.category

        return snapshots, categories_by_market

    def _resolve_open_positions(self, categories_by_market: dict[str, str]) -> dict[str, float]:
        if not self.portfolio.open_positions:
            return {}

        pnl_by_worker: dict[str, float] = {}
        still_open: list[VirtualPosition] = []

        for position in self.portfolio.open_positions:
            details = self._get_json(f"/markets/{position.market_id}")
            resolved, outcome = self._resolution_status(details)
            if not resolved:
                still_open.append(position)
                continue

            payout, profit = self._position_payout(position, outcome)
            self.portfolio.cash += payout
            self.portfolio.total_profit += profit
            pnl_by_worker[position.strategy_id] = pnl_by_worker.get(position.strategy_id, 0.0) + profit

            self.portfolio.closed_positions.append(
                BetRecord(
                    market_id=position.market_id,
                    question=position.question,
                    category=categories_by_market.get(position.market_id, "unknown"),
                    action=position.action,
                    entry_price=position.entry_price,
                    estimated_prob=position.estimated_prob,
                    bet_amount=position.bet_amount,
                    shares=position.shares,
                    outcome=outcome,
                    profit=profit,
                    kelly_fraction=0.0,
                )
            )

        self.portfolio.open_positions = still_open
        return pnl_by_worker

    def _tune_workers(self, resolved_pnl_by_worker: dict[str, float]) -> None:
        if not resolved_pnl_by_worker:
            return

        training_snapshots: list[MarketSnapshot] = []
        training_outcomes: list[float] = []

        for record in reversed(self.portfolio.closed_positions):
            training_snapshots.append(
                MarketSnapshot(
                    market_id=record.market_id,
                    question=record.question,
                    category=record.category,
                    current_price=record.entry_price,
                    price_history=[record.entry_price],
                    days_to_resolution=0.0,
                    tags=[],
                )
            )
            training_outcomes.append(record.outcome)
            if len(training_snapshots) >= 100:
                break

        if not training_snapshots:
            return

        for worker in self.workers:
            if not hasattr(worker, "self_tune"):
                continue
            try:
                worker.self_tune(training_snapshots, training_outcomes, n_candidates=8)
            except TypeError:
                try:
                    worker.self_tune(training_snapshots, training_outcomes)
                except TypeError:
                    worker.self_tune(training_snapshots)

    def _allocate_budget(self, available_cash: float) -> dict[str, float]:
        if not self.workers:
            return {}

        strategy_ids = [worker.strategy_id for worker in self.workers]
        if available_cash <= 0:
            return {sid: 0.0 for sid in strategy_ids}

        unexplored = [sid for sid in strategy_ids if self._obs_count.get(sid, 0) == 0]
        if unexplored:
            share = available_cash / len(unexplored)
            return {sid: (share if sid in unexplored else 0.0) for sid in strategy_ids}

        total_obs = max(1, self._completed_cycles)
        scores: dict[str, float] = {}
        for sid in strategy_ids:
            obs = max(1, self._obs_count.get(sid, 1))
            avg = self._sum_pnl_pct.get(sid, 0.0) / obs
            explore = (2.0 * max(0.0, math.log(total_obs + 1) / obs)) ** 0.5
            scores[sid] = avg + explore

        positive_scores = {sid: max(0.0, score) for sid, score in scores.items()}
        total_score = sum(positive_scores.values())
        if total_score <= 0:
            equal = available_cash / len(strategy_ids)
            return {sid: equal for sid in strategy_ids}

        return {sid: available_cash * (positive_scores[sid] / total_score) for sid in strategy_ids}

    def _evaluate_open_markets(
        self,
        snapshots: list[MarketSnapshot],
    ) -> dict[str, list[tuple[MarketSnapshot, BetDecision]]]:
        decisions: dict[str, list[tuple[MarketSnapshot, BetDecision]]] = {
            worker.strategy_id: [] for worker in self.workers
        }

        for worker in self.workers:
            for snapshot in snapshots:
                decision = self._worker_decision(worker, snapshot)
                decisions[worker.strategy_id].append((snapshot, decision))

        return decisions

    def _place_virtual_bets(
        self,
        decisions: dict[str, list[tuple[MarketSnapshot, BetDecision]]],
        allocations: dict[str, float],
    ) -> dict[str, int]:
        placed_by_worker = {worker.strategy_id: 0 for worker in self.workers}
        if self.dry_run:
            return placed_by_worker

        remaining_by_worker = {sid: float(allocations.get(sid, 0.0)) for sid in allocations}

        for worker in self.workers:
            strategy_id = worker.strategy_id
            for snapshot, decision in decisions.get(strategy_id, []):
                if decision.action == BetAction.PASS:
                    continue
                if strategy_id not in remaining_by_worker:
                    continue
                if self.portfolio.cash <= 0:
                    break

                fraction = kelly_fraction(
                    estimated_prob=float(decision.estimated_probability),
                    market_price=float(snapshot.current_price),
                    confidence=float(decision.confidence),
                    max_fraction=self.config.max_kelly_fraction,
                )
                if fraction <= 0:
                    continue

                capital_base = min(self.portfolio.cash, remaining_by_worker[strategy_id])
                if capital_base <= 0:
                    continue

                bet_amount = capital_base * fraction
                if bet_amount <= 0:
                    continue

                shares = self._shares_for_position(decision.action, bet_amount, snapshot.current_price)
                if shares <= 0:
                    continue

                position = VirtualPosition(
                    market_id=snapshot.market_id,
                    question=snapshot.question,
                    action=decision.action,
                    entry_price=float(snapshot.current_price),
                    bet_amount=float(bet_amount),
                    shares=float(shares),
                    opened_at=datetime.now(tz=timezone.utc),
                    estimated_prob=float(decision.estimated_probability),
                    strategy_id=strategy_id,
                )

                self.portfolio.open_positions.append(position)
                self.portfolio.cash -= bet_amount
                remaining_by_worker[strategy_id] -= bet_amount
                placed_by_worker[strategy_id] = placed_by_worker.get(strategy_id, 0) + 1

        return placed_by_worker

    def _build_cycle_results(
        self,
        allocations: dict[str, float],
        resolved_pnl_by_worker: dict[str, float],
        placed_by_worker: dict[str, int],
    ) -> list[CycleResult]:
        results: list[CycleResult] = []

        for worker in self.workers:
            strategy_id = worker.strategy_id
            initial = float(allocations.get(strategy_id, 0.0))
            pnl = float(resolved_pnl_by_worker.get(strategy_id, 0.0))
            final = initial + pnl
            pnl_pct = (pnl / initial) if initial > 0 else 0.0

            results.append(
                CycleResult(
                    strategy_id=strategy_id,
                    cycle_idx=self._cycle_count,
                    budget_allocated=initial,
                    is_virtual=initial <= 0,
                    initial_equity=initial,
                    final_equity=final,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    score=pnl_pct,
                    params_used=self._worker_params(worker),
                    trade_count=int(placed_by_worker.get(strategy_id, 0)),
                    commission_paid=0.0,
                    slippage_paid=0.0,
                )
            )

        return results

    def _observe_worker(self, strategy_id: str, pnl_pct: float) -> None:
        self._obs_count[strategy_id] = self._obs_count.get(strategy_id, 0) + 1
        self._sum_pnl_pct[strategy_id] = self._sum_pnl_pct.get(strategy_id, 0.0) + float(pnl_pct)

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode(params or {})
        url = f"{self._BASE_URL}{path}"
        if query:
            url = f"{url}?{query}"

        self._wait_for_rate_limit()

        try:
            with urllib.request.urlopen(url) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise RuntimeError(f"Polymarket request failed: HTTP {status} for {url}")
                payload = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Polymarket request failed: HTTP {exc.code} for {url}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Polymarket request failed: network error ({exc.reason})") from exc

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Polymarket request failed: malformed JSON for {url}") from exc

    def _wait_for_rate_limit(self) -> None:
        now = time.monotonic()
        if self._last_request_ts is not None:
            elapsed = now - self._last_request_ts
            wait = self._MIN_REQUEST_INTERVAL_SECONDS - elapsed
            if wait > 0:
                time.sleep(wait)
        self._last_request_ts = time.monotonic()

    @staticmethod
    def _extract_market_list(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("data", "markets"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _market_id(raw_market: dict[str, Any]) -> str:
        return str(
            raw_market.get("id")
            or raw_market.get("market_id")
            or raw_market.get("condition_id")
            or raw_market.get("conditionId")
            or ""
        )

    @staticmethod
    def _extract_market_price(raw_market: dict[str, Any]) -> float | None:
        for key in ("lastTradePrice", "price", "probability", "currentPrice"):
            value = raw_market.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _extract_tags(raw_market: dict[str, Any]) -> list[str]:
        tags = raw_market.get("tags") or []
        if isinstance(tags, str):
            return [tags]
        if isinstance(tags, list):
            return [str(tag) for tag in tags]
        return []

    @staticmethod
    def _extract_price_history(payload: Any) -> list[float]:
        rows: list[Any]
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            history = payload.get("history")
            rows = history if isinstance(history, list) else []
        else:
            rows = []

        points: list[tuple[float, float]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue

            price_value = row.get("p")
            if price_value is None:
                price_value = row.get("price")
            if price_value is None:
                price_value = row.get("probability")

            ts_value = row.get("t")
            if ts_value is None:
                ts_value = row.get("timestamp")
            if ts_value is None:
                ts_value = row.get("time")

            try:
                price = float(price_value)
                ts = float(ts_value)
            except (TypeError, ValueError):
                continue

            points.append((ts, price))

        points.sort(key=lambda item: item[0])
        return [price for _, price in points]

    @staticmethod
    def _days_to_resolution(raw_market: dict[str, Any]) -> float:
        candidates = [
            raw_market.get("endDate"),
            raw_market.get("end_date"),
            raw_market.get("resolved_at"),
            raw_market.get("resolvedAt"),
        ]
        for value in candidates:
            dt = PolymarketPaperSession._parse_datetime(value)
            if dt is None:
                continue
            delta = dt - datetime.now(tz=timezone.utc)
            return max(0.0, delta.total_seconds() / 86_400.0)
        return 0.0

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)

        if isinstance(value, str) and value:
            candidate = value
            if candidate.endswith("Z"):
                candidate = f"{candidate[:-1]}+00:00"
            try:
                parsed = datetime.fromisoformat(candidate)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)

        return None

    @staticmethod
    def _resolution_status(payload: Any) -> tuple[bool, float]:
        if not isinstance(payload, dict):
            return False, 0.0

        resolved = bool(payload.get("resolved") or payload.get("closed") or payload.get("isResolved"))

        outcome_raw = (
            payload.get("outcome")
            or payload.get("resolvedOutcome")
            or payload.get("winningOutcome")
            or payload.get("winner")
        )

        if outcome_raw is None:
            return resolved, 0.0

        if isinstance(outcome_raw, str):
            normalized = outcome_raw.strip().lower()
            if normalized in {"yes", "true", "1"}:
                return True, 1.0
            if normalized in {"no", "false", "0"}:
                return True, 0.0

        try:
            numeric = float(outcome_raw)
        except (TypeError, ValueError):
            return resolved, 0.0

        return True, 1.0 if numeric >= 0.5 else 0.0

    @staticmethod
    def _position_payout(position: VirtualPosition, outcome: float) -> tuple[float, float]:
        if position.action == BetAction.BET_YES and outcome >= 0.5:
            payout = position.shares
        elif position.action == BetAction.BET_NO and outcome < 0.5:
            payout = position.shares
        else:
            payout = 0.0

        profit = payout - position.bet_amount
        return payout, profit

    @staticmethod
    def _shares_for_position(action: BetAction, bet_amount: float, price: float) -> float:
        if action == BetAction.BET_YES:
            if price <= 0:
                return 0.0
            return bet_amount / price

        if action == BetAction.BET_NO:
            no_price = 1.0 - price
            if no_price <= 0:
                return 0.0
            return bet_amount / no_price

        return 0.0

    @staticmethod
    def _worker_params(worker: WorkerAgent) -> dict[str, Any]:
        params = getattr(worker, "_current_params", None)
        if isinstance(params, dict):
            return dict(params)

        checkpoint = getattr(worker, "checkpoint", None)
        if callable(checkpoint):
            state = checkpoint()
            if isinstance(state, dict) and isinstance(state.get("current_params"), dict):
                return dict(state["current_params"])

        return {}

    def _worker_decision(self, worker: WorkerAgent, snapshot: MarketSnapshot) -> BetDecision:
        evaluate_market = getattr(worker, "evaluate_market", None)
        if callable(evaluate_market):
            decision = evaluate_market(snapshot)
            if isinstance(decision, BetDecision):
                return decision

        strategy = getattr(worker, "strategy", None)
        if strategy is not None and hasattr(strategy, "evaluate"):
            params = self._worker_params(worker)
            decision = strategy.evaluate(snapshot, params)
            if isinstance(decision, BetDecision):
                return decision

        return BetDecision(
            action=BetAction.PASS,
            estimated_probability=float(snapshot.current_price),
            confidence=0.0,
            reasoning="worker has no polymarket evaluation hook",
        )

    def _portfolio_value(self, current_prices: dict[str, float] | None = None) -> float:
        current_prices = current_prices or {}
        value = float(self.portfolio.cash)

        for position in self.portfolio.open_positions:
            price = float(current_prices.get(position.market_id, position.entry_price))
            if position.action == BetAction.BET_YES:
                value += position.shares * price
            elif position.action == BetAction.BET_NO:
                value += position.shares * (1.0 - price)

        return value

    @staticmethod
    def _virtual_position_to_dict(position: VirtualPosition) -> dict[str, Any]:
        return {
            "market_id": position.market_id,
            "question": position.question,
            "action": position.action.value,
            "entry_price": position.entry_price,
            "bet_amount": position.bet_amount,
            "shares": position.shares,
            "opened_at": position.opened_at.isoformat(),
            "estimated_prob": position.estimated_prob,
            "strategy_id": position.strategy_id,
        }

    @staticmethod
    def _virtual_position_from_dict(payload: dict[str, Any]) -> VirtualPosition:
        opened_at_raw = payload.get("opened_at")
        opened_at = PolymarketPaperSession._parse_datetime(opened_at_raw) or datetime.now(tz=timezone.utc)

        return VirtualPosition(
            market_id=str(payload.get("market_id", "")),
            question=str(payload.get("question", "")),
            action=BetAction(str(payload.get("action", BetAction.PASS.value))),
            entry_price=float(payload.get("entry_price", 0.0)),
            bet_amount=float(payload.get("bet_amount", 0.0)),
            shares=float(payload.get("shares", 0.0)),
            opened_at=opened_at,
            estimated_prob=float(payload.get("estimated_prob", 0.0)),
            strategy_id=str(payload.get("strategy_id", "")),
        )

    @staticmethod
    def _bet_record_to_dict(record: BetRecord) -> dict[str, Any]:
        return {
            "market_id": record.market_id,
            "question": record.question,
            "category": record.category,
            "action": record.action.value,
            "entry_price": record.entry_price,
            "estimated_prob": record.estimated_prob,
            "bet_amount": record.bet_amount,
            "shares": record.shares,
            "outcome": record.outcome,
            "profit": record.profit,
            "kelly_fraction": record.kelly_fraction,
        }

    @staticmethod
    def _bet_record_from_dict(payload: dict[str, Any]) -> BetRecord:
        return BetRecord(
            market_id=str(payload.get("market_id", "")),
            question=str(payload.get("question", "")),
            category=str(payload.get("category", "unknown")),
            action=BetAction(str(payload.get("action", BetAction.PASS.value))),
            entry_price=float(payload.get("entry_price", 0.0)),
            estimated_prob=float(payload.get("estimated_prob", 0.0)),
            bet_amount=float(payload.get("bet_amount", 0.0)),
            shares=float(payload.get("shares", 0.0)),
            outcome=float(payload.get("outcome", 0.0)),
            profit=float(payload.get("profit", 0.0)),
            kelly_fraction=float(payload.get("kelly_fraction", 0.0)),
        )

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
        results = [
            CycleResult(
                strategy_id=str(item.get("strategy_id", "")),
                cycle_idx=int(item.get("cycle_idx", 0)),
                budget_allocated=float(item.get("budget_allocated", 0.0)),
                is_virtual=bool(item.get("is_virtual", True)),
                initial_equity=float(item.get("initial_equity", 0.0)),
                final_equity=float(item.get("final_equity", 0.0)),
                pnl=float(item.get("pnl", 0.0)),
                pnl_pct=float(item.get("pnl_pct", 0.0)),
                score=float(item.get("score", 0.0)),
                params_used=dict(item.get("params_used", {})),
                trade_count=int(item.get("trade_count", 0)),
                commission_paid=float(item.get("commission_paid", 0.0)),
                slippage_paid=float(item.get("slippage_paid", 0.0)),
            )
            for item in payload.get("results", [])
            if isinstance(item, dict)
        ]

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
