# DEPRECATED: replaced by scripts/fetch_crypto_data.py
# This file generates synthetic random-walk data for offline testing only.

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True)
class AssetConfig:
    output_path: Path
    start_price: float
    drift: float
    volatility: float
    avg_volume: float
    std_volume: float
    volume_floor: float
    seed: int


START_DATE = date(2020, 1, 1)
ROWS = 1000

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "trading"


BTC_CONFIG = AssetConfig(
    output_path=DATA_DIR / "btc_usdt_1d.csv",
    start_price=7200.0,
    drift=0.0003,
    volatility=0.025,
    avg_volume=25_000_000.0,
    std_volume=5_000_000.0,
    volume_floor=5_000_000.0,
    seed=42,
)

ETH_CONFIG = AssetConfig(
    output_path=DATA_DIR / "eth_usdt_1d.csv",
    start_price=130.0,
    drift=0.0004,
    volatility=0.032,
    avg_volume=10_000_000.0,
    std_volume=2_000_000.0,
    volume_floor=1_000_000.0,
    seed=43,
)


def round2(value: float) -> float:
    return float(f"{value:.2f}")


def generate_rows(config: AssetConfig) -> list[list[str]]:
    rng = random.Random(config.seed)
    prev_close = config.start_price
    rows: list[list[str]] = []

    for i in range(ROWS):
        current_date = START_DATE + timedelta(days=i)

        log_return = rng.gauss(config.drift, config.volatility)
        close = prev_close * math.exp(log_return)
        open_ = prev_close * math.exp(rng.gauss(0, config.volatility * 0.3))
        high = max(open_, close) * (1 + abs(rng.gauss(0, config.volatility * 0.5)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, config.volatility * 0.5)))
        volume = max(config.volume_floor, rng.gauss(config.avg_volume, config.std_volume))

        open_r = round2(open_)
        close_r = round2(close)
        high_r = round2(high)
        low_r = round2(low)
        volume_r = round2(volume)

        high_r = max(high_r, open_r, close_r)
        low_r = min(low_r, open_r, close_r)

        rows.append(
            [
                current_date.isoformat(),
                f"{open_r:.2f}",
                f"{high_r:.2f}",
                f"{low_r:.2f}",
                f"{close_r:.2f}",
                f"{volume_r:.2f}",
            ]
        )

        prev_close = close

    return rows


def write_csv(config: AssetConfig) -> None:
    rows = generate_rows(config)
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    with config.output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        writer.writerows(rows)


def main() -> None:
    write_csv(BTC_CONFIG)
    write_csv(ETH_CONFIG)


if __name__ == "__main__":
    main()
