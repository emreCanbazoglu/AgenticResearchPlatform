from __future__ import annotations

import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://api.binance.com/api/v3/klines"
LIMIT = 1000
INTERVAL = "1d"
CSV_COLUMNS = ["open_time", "open", "high", "low", "close", "volume"]

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "trading"
OUTPUT_FILES = {
    "BTCUSDT": DATA_DIR / "btc_usdt_1d.csv",
    "ETHUSDT": DATA_DIR / "eth_usdt_1d.csv",
    "BTCUSDT_30m": DATA_DIR / "btc_usdt_30m.csv",
    "ETHUSDT_30m": DATA_DIR / "eth_usdt_30m.csv",
}


class DataFetchError(Exception):
    pass


def fetch_klines(symbol: str, interval: str = INTERVAL, limit: int = LIMIT) -> list[list[object]]:
    url = f"{BASE_URL}?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        with urllib.request.urlopen(url) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise DataFetchError(f"HTTP {status} for {symbol}")
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise DataFetchError(f"HTTP error for {symbol}: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise DataFetchError(f"Network error for {symbol}: {exc.reason}") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DataFetchError(f"Malformed JSON response for {symbol}") from exc

    if not isinstance(data, list):
        raise DataFetchError(f"Malformed response for {symbol}: expected a list")
    if len(data) == 0:
        raise DataFetchError(f"Empty response for {symbol}")

    for index, row in enumerate(data):
        if not isinstance(row, list) or len(row) < 6:
            raise DataFetchError(f"Malformed row {index} for {symbol}")
        try:
            int(row[0])
            float(row[1])
            float(row[2])
            float(row[3])
            float(row[4])
            float(row[5])
        except (TypeError, ValueError) as exc:
            raise DataFetchError(f"Malformed numeric fields in row {index} for {symbol}") from exc

    return data


def write_csv(rows: list[list[object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow([row[0], row[1], row[2], row[3], row[4], row[5]])


def fetch_and_write_symbol(symbol: str, output_path: Path) -> int:
    interval = INTERVAL
    binance_symbol = symbol
    if symbol.endswith("_30m"):
        interval = "30m"
        binance_symbol = symbol.removesuffix("_30m")

    rows = fetch_klines(binance_symbol, interval=interval)
    write_csv(rows, output_path)
    try:
        display_path = output_path.relative_to(ROOT_DIR)
    except ValueError:
        display_path = output_path
    print(f"Fetched {len(rows)} rows for {symbol} -> {display_path}")
    return len(rows)


def main() -> int:
    try:
        for symbol, output_path in OUTPUT_FILES.items():
            fetch_and_write_symbol(symbol, output_path)
    except DataFetchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
