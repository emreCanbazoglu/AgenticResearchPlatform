from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]

from domains.polymarket.base import MarketSnapshot

MODEL_NAME = "claude-3-5-haiku-20241022"
SYSTEM_PROMPT = """You are a calibrated probability forecaster specialising in prediction markets.
Your task is to estimate the probability that a given event will resolve YES.

Rules:
- Return only a JSON object — no markdown, no explanation outside the JSON
- Be well-calibrated: a 70% estimate means roughly 7 in 10 similar events resolve YES
- Account for base rates, not just current news
- Express genuine uncertainty — most events should be between 15% and 85%
- Confidence reflects how much information you have, not how extreme your estimate is

Output format:
{
  "probability": 0.65,
  "confidence": 0.7,
  "reasoning": "One to three sentence explanation."
}"""


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _extract_text(response: Any) -> str:
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        return ""

    chunks: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            chunks.append(text)
    return "\n".join(chunks).strip()


def _parse_json_object(raw: str) -> dict[str, Any]:
    candidate = raw.strip()
    if candidate.startswith("```"):
        stripped = candidate.strip("`")
        candidate = stripped.replace("json\n", "", 1).strip()

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object")

    payload_raw = candidate[start : end + 1]
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response JSON parse failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("LLM response JSON must be an object")
    return payload


def _history_summary(snapshot: MarketSnapshot) -> str:
    now = datetime.now(UTC)
    recent = snapshot.price_history[-10:]
    if not recent:
        recent = [snapshot.current_price]

    lines: list[str] = []
    for idx, value in enumerate(recent):
        days_back = len(recent) - idx
        label = (now.replace(hour=0, minute=0, second=0, microsecond=0)).date()
        label = label.fromordinal(label.toordinal() - days_back)
        lines.append(f"{label.strftime('%b %d')}: {round(_clamp01(float(value)) * 100):.0f}%")
    return "  ".join(lines)


@dataclass
class LLMEstimate:
    market_id: str
    question: str
    market_price: float
    estimated_probability: float
    confidence: float
    reasoning: str
    model: str
    estimated_at: datetime


@dataclass
class MispricedMarket:
    market_id: str
    question: str
    market_price: float
    llm_estimate: float
    deviation: float
    direction: str
    confidence: float
    reasoning: str


class LLMEvaluator:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = MODEL_NAME,
        cache_dir: str | Path = "data/polymarket/llm_estimates",
        max_daily_markets: int = 100,
        client: Any | None = None,
    ) -> None:
        if client is not None:
            self.client = client
        else:
            if anthropic is None:
                raise RuntimeError("anthropic SDK is required for LLMEvaluator")
            self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.cache_dir = Path(cache_dir)
        self.max_daily_markets = max(0, int(max_daily_markets))

    def estimate(self, market_snapshot: MarketSnapshot) -> LLMEstimate:
        tags = ", ".join(market_snapshot.tags) if market_snapshot.tags else "none"
        user_prompt = (
            f"Market: {market_snapshot.question}\n"
            f"Category: {market_snapshot.category}\n"
            f"Current market price (implied probability): {market_snapshot.current_price:.1%}\n"
            f"Days until resolution: {market_snapshot.days_to_resolution:.0f}\n"
            f"Tags: {tags}\n\n"
            "Price history (last 10 data points, oldest first):\n"
            f"{_history_summary(market_snapshot)}\n\n"
            "Estimate the probability this market resolves YES."
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = _extract_text(response)
        payload = _parse_json_object(raw_text)

        probability = _clamp01(float(payload["probability"]))
        confidence = _clamp01(float(payload["confidence"]))
        reasoning = str(payload["reasoning"]).strip()

        return LLMEstimate(
            market_id=market_snapshot.market_id,
            question=market_snapshot.question,
            market_price=_clamp01(float(market_snapshot.current_price)),
            estimated_probability=probability,
            confidence=confidence,
            reasoning=reasoning,
            model=self.model,
            estimated_at=datetime.now(UTC),
        )

    def batch_estimate(self, snapshots: list[MarketSnapshot]) -> list[LLMEstimate]:
        today = datetime.now(UTC).date()
        cache_path = self.cache_dir / f"{today.isoformat()}.json"
        cached = self.load_estimates(cache_path)
        by_market_id = {item.market_id: item for item in cached}

        to_query = [snapshot for snapshot in snapshots if snapshot.market_id not in by_market_id]
        if len(to_query) > self.max_daily_markets:
            to_query = to_query[: self.max_daily_markets]

        fresh: dict[str, LLMEstimate] = {}
        workers = min(5, len(to_query))
        if workers > 0:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(self.estimate, snapshot): snapshot.market_id for snapshot in to_query}
                for future in as_completed(futures):
                    result = future.result()
                    fresh[result.market_id] = result

        combined = {**by_market_id, **fresh}
        self.save_estimates(cache_path, list(combined.values()))
        return [combined[snapshot.market_id] for snapshot in snapshots if snapshot.market_id in combined]

    def flag_mispriced(
        self,
        snapshots: list[MarketSnapshot],
        threshold: float = 0.10,
    ) -> list[MispricedMarket]:
        estimates = self.batch_estimate(snapshots)
        by_market_id = {item.market_id: item for item in estimates}

        flagged: list[MispricedMarket] = []
        threshold_value = abs(float(threshold))
        for snapshot in snapshots:
            estimate = by_market_id.get(snapshot.market_id)
            if estimate is None:
                continue

            deviation = estimate.estimated_probability - snapshot.current_price
            if abs(deviation) <= threshold_value:
                continue

            flagged.append(
                MispricedMarket(
                    market_id=snapshot.market_id,
                    question=snapshot.question,
                    market_price=_clamp01(float(snapshot.current_price)),
                    llm_estimate=_clamp01(float(estimate.estimated_probability)),
                    deviation=float(deviation),
                    direction="underpriced" if deviation > 0 else "overpriced",
                    confidence=_clamp01(float(estimate.confidence)),
                    reasoning=estimate.reasoning,
                )
            )

        return sorted(flagged, key=lambda item: abs(item.deviation), reverse=True)

    def save_estimates(self, path: str | Path, estimates: list[LLMEstimate]) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = [
            {
                "market_id": item.market_id,
                "question": item.question,
                "market_price": item.market_price,
                "estimated_probability": item.estimated_probability,
                "confidence": item.confidence,
                "reasoning": item.reasoning,
                "model": item.model,
                "estimated_at": _as_utc(item.estimated_at).isoformat(),
            }
            for item in estimates
        ]
        payload.sort(key=lambda item: str(item["market_id"]))
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_estimates(self, path: str | Path) -> list[LLMEstimate]:
        target = Path(path)
        if not target.exists():
            return []

        raw = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("estimate cache must be a JSON list")

        estimates: list[LLMEstimate] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            estimates.append(
                LLMEstimate(
                    market_id=str(item["market_id"]),
                    question=str(item["question"]),
                    market_price=_clamp01(float(item["market_price"])),
                    estimated_probability=_clamp01(float(item["estimated_probability"])),
                    confidence=_clamp01(float(item["confidence"])),
                    reasoning=str(item.get("reasoning", "")),
                    model=str(item.get("model", self.model)),
                    estimated_at=_as_utc(datetime.fromisoformat(str(item["estimated_at"]))),
                )
            )
        return estimates
