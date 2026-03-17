from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKETS_URL = "https://gamma-api.polymarket.com/markets"
PRICE_HISTORY_URL = "https://clob.polymarket.com/prices-history"
REQUEST_DELAY_SECONDS = 1.0
# CLOB price history max window in seconds (API rejects windows > ~3 days)
PRICE_HISTORY_WINDOW_SECONDS = 60 * 60 * 24 * 3

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT_DIR / "data" / "polymarket"


class FetchError(Exception):
    pass


def _get_json(url: str, params: dict[str, Any]) -> Any:
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}" if query else url

    req = urllib.request.Request(
        full_url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; polymarket-fetcher/1.0)"},
    )
    try:
        with urllib.request.urlopen(req) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise FetchError(f"HTTP {status} for {full_url}")
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP error for {full_url}: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FetchError(f"Network error for {full_url}: {exc.reason}") from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FetchError(f"Malformed JSON for {full_url}") from exc


def _iso_utc(value: Any) -> str:
    if isinstance(value, str) and value:
        if value.endswith("Z"):
            return value
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            return value

    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value = value / 1000
        parsed = datetime.fromtimestamp(value, tz=timezone.utc)
        return parsed.isoformat().replace("+00:00", "Z")

    return ""


def _normalize_market(raw: dict[str, Any]) -> dict[str, Any]:
    market_id = str(raw.get("market_id") or raw.get("id") or raw.get("conditionId") or "")
    question = str(raw.get("question") or raw.get("title") or "")
    # Derive category from sportsMarketType, falling back to the category field
    raw_category = raw.get("category") or ""
    sports_type = raw.get("sportsMarketType") or ""
    if sports_type:
        # e.g. "tennis_match_totals" -> "tennis", "dota2_rampage" -> "esports"
        prefix = sports_type.split("_")[0]
        if prefix in ("tennis", "nba", "nfl", "nhl", "mlb", "soccer", "golf"):
            category = prefix
        elif prefix in ("dota2", "csgo", "lol", "valorant"):
            category = "esports"
        else:
            category = "sports"
    elif raw_category:
        category = raw_category.lower()
    else:
        # Infer from question text
        q = str(raw.get("question") or "").lower()
        if any(w in q for w in ["election", "president", "vote", "congress", "senate", "governor"]):
            category = "politics"
        elif any(w in q for w in ["bitcoin", "btc", "eth", "crypto", "solana", "xrp"]):
            category = "crypto"
        elif any(w in q for w in ["netflix", "oscar", "movie", "box office", "grammy"]):
            category = "entertainment"
        elif any(w in q for w in ["fed", "gdp", "inflation", "rate", "recession", "economy"]):
            category = "economics"
        else:
            category = "other"
    created_at = _iso_utc(raw.get("created_at") or raw.get("createdAt") or raw.get("start_date"))
    # Gamma API uses closedTime for when the market resolved
    resolved_at = _iso_utc(
        raw.get("closedTime") or raw.get("resolved_at") or raw.get("end_date") or raw.get("resolvedAt")
    )

    # Gamma API: outcomePrices is ["1","0"] for YES resolved, ["0","1"] for NO resolved
    outcome = raw.get("outcome")
    if outcome is None:
        outcome_prices_raw = raw.get("outcomePrices")
        if isinstance(outcome_prices_raw, str):
            try:
                outcome_prices = json.loads(outcome_prices_raw)
            except (json.JSONDecodeError, ValueError):
                outcome_prices = []
        elif isinstance(outcome_prices_raw, list):
            outcome_prices = outcome_prices_raw
        else:
            outcome_prices = []

        if outcome_prices:
            try:
                yes_price = float(outcome_prices[0])
                outcome = 1.0 if yes_price >= 0.5 else 0.0
            except (TypeError, ValueError):
                outcome = 0.0
        else:
            resolved = raw.get("resolvedOutcome")
            if isinstance(resolved, str):
                outcome = 1.0 if resolved.lower() == "yes" else 0.0
            else:
                outcome = 0.0

    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        tags = []

    # Extract YES token ID (first entry in clobTokenIds) for price history fetching
    clob_token_ids_raw = raw.get("clobTokenIds", "[]")
    if isinstance(clob_token_ids_raw, str):
        try:
            clob_token_ids = json.loads(clob_token_ids_raw)
        except (json.JSONDecodeError, ValueError):
            clob_token_ids = []
    elif isinstance(clob_token_ids_raw, list):
        clob_token_ids = clob_token_ids_raw
    else:
        clob_token_ids = []

    yes_token = str(clob_token_ids[0]) if clob_token_ids else ""

    return {
        "market_id": market_id,
        "question": question,
        "category": category,
        "created_at": created_at,
        "resolved_at": resolved_at,
        "outcome": float(outcome),
        "tags": [str(tag) for tag in tags],
        "yes_token": yes_token,
    }


def fetch_markets(
    limit: int = 500,
    category: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict[str, Any]]:
    # Gamma API uses closed=true (not resolved=true) and returns a list
    params: dict[str, Any] = {"closed": "true", "limit": limit, "order": "closedTime", "ascending": "false"}
    if category:
        params["category"] = category
    # end_date_min / end_date_max filter on the market's resolution/close date
    if from_date:
        params["end_date_min"] = from_date
    if to_date:
        params["end_date_max"] = to_date

    data = _get_json(MARKETS_URL, params)
    if not isinstance(data, list):
        raise FetchError("Unexpected markets payload: expected a list")

    markets = [_normalize_market(item) for item in data if isinstance(item, dict)]
    markets = [item for item in markets if item["market_id"]]
    return markets


def _extract_price_points(payload: Any) -> list[tuple[str, float]]:
    rows: list[Any]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        history = payload.get("history")
        rows = history if isinstance(history, list) else []
    else:
        rows = []

    points: list[tuple[str, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        timestamp = _iso_utc(row.get("timestamp") or row.get("t") or row.get("time"))
        probability_raw = row.get("probability")
        if probability_raw is None:
            probability_raw = row.get("price") if row.get("price") is not None else row.get("p")
        if not timestamp or probability_raw is None:
            continue
        try:
            probability = float(probability_raw)
        except (TypeError, ValueError):
            continue
        points.append((timestamp, probability))

    points.sort(key=lambda item: item[0])
    return points


def fetch_price_history(yes_token: str, resolved_at_iso: str) -> list[tuple[str, float]]:
    """
    Fetch price history using the YES token ID and a time window around resolution.
    CLOB API requires startTs/endTs (unix seconds) and rejects windows > ~3 days.
    We fetch the 3-day window ending at resolution time.
    """
    if not yes_token:
        return []

    # Parse resolved_at to unix timestamp
    try:
        if resolved_at_iso.endswith("Z"):
            resolved_at_iso = resolved_at_iso[:-1] + "+00:00"
        end_ts = int(datetime.fromisoformat(resolved_at_iso).timestamp())
    except (ValueError, AttributeError):
        return []

    start_ts = end_ts - PRICE_HISTORY_WINDOW_SECONDS

    payload = _get_json(PRICE_HISTORY_URL, {
        "market": yes_token,
        "startTs": start_ts,
        "endTs": end_ts,
        "fidelity": 60,
    })
    return _extract_price_points(payload)


def write_markets_json(markets: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(markets, file, indent=2)


def write_price_csv(path: Path, points: list[tuple[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "probability"])
        writer.writerows(points)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch historical resolved Polymarket data")
    parser.add_argument("--category", type=str, default=None, help="Filter markets by category")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing files")
    parser.add_argument("--limit", type=int, default=500, help="Maximum resolved markets to fetch")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Output data directory")
    parser.add_argument(
        "--from-date",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="Only include markets that closed ON OR AFTER this date (end_date_min)",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="Only include markets that closed ON OR BEFORE this date (end_date_max)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        markets = fetch_markets(
            limit=args.limit,
            category=args.category,
            from_date=args.from_date,
            to_date=args.to_date,
        )
    except FetchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Fetching resolved markets... {len(markets)} found")

    markets_path = args.data_dir / "markets.json"
    if args.dry_run:
        print(f"[DRY-RUN] Would write {markets_path}")
    else:
        print(f"Writing {markets_path}")
        write_markets_json(markets, markets_path)

    with_histories = 0
    total = len(markets)
    print(f"Fetching price histories: {total}/{total}")

    for market in markets:
        market_id = market["market_id"]
        question = market["question"]
        short_question = question if len(question) <= 50 else f"{question[:47]}..."

        yes_token = market.get("yes_token", "")
        resolved_at = market.get("resolved_at", "")

        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            points = fetch_price_history(yes_token, resolved_at)
        except FetchError:
            points = []

        if not points:
            print(f"  [SKIP] {market_id} - no price history available")
            continue

        with_histories += 1
        if args.dry_run:
            print(f"  [DRY-RUN] {market_id} - {short_question} ({len(points)} price points)")
            continue

        output_path = args.data_dir / "price_histories" / f"{market_id}.csv"
        write_price_csv(output_path, points)
        print(f"  [OK] {market_id} - {short_question} ({len(points)} price points)")

    print(f"Done. {with_histories} markets with price histories written to {args.data_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
