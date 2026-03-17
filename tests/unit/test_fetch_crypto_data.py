from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "fetch_crypto_data.py"
    spec = importlib.util.spec_from_file_location("fetch_crypto_data", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeHTTPResponse:
    def __init__(self, payload: bytes, status: int = 200):
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_csv_written_correctly(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_rows = [
        [1609459200000, "29000.0", "29300.0", "28800.0", "29100.0", "5000.0"],
        [1609545600000, "29100.0", "29600.0", "28900.0", "29500.0", "6200.0"],
        [1609632000000, "29500.0", "30000.0", "29400.0", "29900.0", "7100.0"],
    ]
    payload = json.dumps(fake_rows).encode("utf-8")

    def fake_urlopen(url: str):
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(module, "LIMIT", 3)

    output_path = tmp_path / "btc_usdt_1d.csv"
    module.fetch_and_write_symbol("BTCUSDT", output_path)

    with output_path.open("r", encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 3
    assert list(rows[0].keys()) == ["open_time", "open", "high", "low", "close", "volume"]
    float(rows[0]["close"])


def test_missing_data_dir_is_created(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_rows = [
        [1609459200000, "1800.0", "1850.0", "1750.0", "1825.0", "10000.0"],
        [1609545600000, "1825.0", "1860.0", "1800.0", "1840.0", "11000.0"],
        [1609632000000, "1840.0", "1880.0", "1830.0", "1875.0", "9000.0"],
    ]
    payload = json.dumps(fake_rows).encode("utf-8")

    def fake_urlopen(url: str):
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(module, "LIMIT", 3)

    output_path = tmp_path / "nonexistent" / "subdir" / "eth_usdt_1d.csv"
    module.fetch_and_write_symbol("ETHUSDT", output_path)

    assert output_path.parent.exists()
    assert output_path.exists()


def test_30m_interval_used_in_url(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_rows = [
        [1609459200000, "29000.0", "29300.0", "28800.0", "29100.0", "5000.0"],
        [1609461000000, "29100.0", "29400.0", "28900.0", "29200.0", "5100.0"],
        [1609462800000, "29200.0", "29500.0", "29000.0", "29300.0", "5200.0"],
    ]
    payload = json.dumps(fake_rows).encode("utf-8")
    captured_url = {"value": ""}

    def fake_urlopen(url: str):
        captured_url["value"] = url
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(module, "LIMIT", 3)

    output_path = tmp_path / "btc_usdt_30m.csv"
    module.fetch_and_write_symbol("BTCUSDT_30m", output_path)

    assert "interval=30m" in captured_url["value"]


def test_30m_output_file_has_correct_header(tmp_path, monkeypatch) -> None:
    module = _load_module()
    fake_rows = [
        [1609459200000, "1800.0", "1850.0", "1750.0", "1825.0", "10000.0"],
        [1609461000000, "1825.0", "1860.0", "1800.0", "1840.0", "11000.0"],
        [1609462800000, "1840.0", "1880.0", "1830.0", "1875.0", "9000.0"],
    ]
    payload = json.dumps(fake_rows).encode("utf-8")

    def fake_urlopen(url: str):
        return _FakeHTTPResponse(payload)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(module, "LIMIT", 3)

    output_path = tmp_path / "eth_usdt_30m.csv"
    module.fetch_and_write_symbol("ETHUSDT_30m", output_path)

    with output_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file)
        header = next(reader)

    assert header == ["open_time", "open", "high", "low", "close", "volume"]
