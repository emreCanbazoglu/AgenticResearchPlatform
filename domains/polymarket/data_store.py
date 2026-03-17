from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class MarketRecord:
    market_id: str
    question: str
    category: str
    created_at: datetime
    resolved_at: datetime
    outcome: float
    tags: list[str]


@dataclass
class PricePoint:
    timestamp: datetime
    probability: float


class HistoricalMarketStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def load_all(self) -> list[MarketRecord]:
        markets_path = self.data_dir / "markets.json"
        with markets_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        records: list[MarketRecord] = [self._parse_market_record(item) for item in payload]
        return sorted(records, key=lambda record: record.resolved_at)

    def get_price_series(self, market_id: str) -> list[PricePoint]:
        csv_path = self.data_dir / "price_histories" / f"{market_id}.csv"
        if not csv_path.exists():
            return []

        points: list[PricePoint] = []
        with csv_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                points.append(
                    PricePoint(
                        timestamp=_parse_iso8601(row["timestamp"]),
                        probability=float(row["probability"]),
                    )
                )

        return sorted(points, key=lambda point: point.timestamp)

    def get_by_category(self, category: str) -> list[MarketRecord]:
        return [record for record in self.load_all() if record.category == category]

    def get_resolved_before(self, cutoff: datetime) -> list[MarketRecord]:
        return [record for record in self.load_all() if record.resolved_at < cutoff]

    def get_resolved_between(self, start: datetime, end: datetime) -> list[MarketRecord]:
        return [record for record in self.load_all() if start <= record.resolved_at <= end]

    def _parse_market_record(self, payload: dict[str, object]) -> MarketRecord:
        tags = payload.get("tags", [])
        if not isinstance(tags, list):
            raise ValueError("tags must be a list")

        return MarketRecord(
            market_id=str(payload["market_id"]),
            question=str(payload["question"]),
            category=str(payload["category"]),
            created_at=_parse_iso8601(str(payload["created_at"])),
            resolved_at=_parse_iso8601(str(payload["resolved_at"])),
            outcome=float(payload["outcome"]),
            tags=[str(tag) for tag in tags],
        )


def _parse_iso8601(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))
