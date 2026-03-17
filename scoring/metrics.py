from __future__ import annotations

import math
from pathlib import Path
from statistics import mean, stdev


DEFAULT_WEIGHTS = {"return_weight": 0.4, "sharpe_weight": 0.4, "drawdown_weight": 0.2}
_SCORING_WEIGHTS_CACHE: dict[str, dict[str, float]] = {}


def profitability_score(initial_equity: float, final_equity: float) -> float:
    if initial_equity <= 0:
        raise ValueError("initial_equity must be > 0")
    return (final_equity - initial_equity) / initial_equity


def max_drawdown(equity_curve: list[float]) -> float:
    if len(equity_curve) < 2:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for equity in equity_curve[1:]:
        if equity > peak:
            peak = equity
            continue
        if peak > 0:
            drawdown = (peak - equity) / peak
            if drawdown > max_dd:
                max_dd = drawdown
    return max_dd


def annualized_volatility(daily_returns: list[float], periods_per_year: int = 365) -> float:
    if len(daily_returns) < 2:
        return 0.0
    return stdev(daily_returns) * math.sqrt(periods_per_year)


def sharpe_ratio(
    daily_returns: list[float], risk_free_rate: float = 0.0, periods_per_year: int = 365
) -> float:
    if len(daily_returns) < 2:
        return 0.0

    avg_return = mean(daily_returns)
    avg_excess_return = avg_return - (risk_free_rate / periods_per_year)
    volatility = stdev(daily_returns)
    if volatility == 0:
        return avg_excess_return * math.sqrt(periods_per_year) if avg_excess_return > 0 else 0.0
    return (avg_excess_return / volatility) * math.sqrt(periods_per_year)


def win_rate(trade_pnls: list[float]) -> float:
    if not trade_pnls:
        return 0.0
    wins = sum(1 for pnl in trade_pnls if pnl > 0)
    return wins / len(trade_pnls)


def composite_score(metrics: dict[str, float], weights: dict[str, float]) -> float:
    return_weight = weights.get("return", weights.get("return_weight", 0.0))
    sharpe_weight = weights.get("sharpe", weights.get("sharpe_weight", 0.0))
    drawdown_weight = weights.get("drawdown", weights.get("drawdown_weight", 0.0))
    return (
        return_weight * metrics.get("total_return", 0.0)
        + sharpe_weight * metrics.get("sharpe_ratio", 0.0)
        - drawdown_weight * metrics.get("max_drawdown", 0.0)
    )


def load_scoring_weights(path: str = "config/scoring.yaml") -> dict[str, float]:
    resolved_path = str(Path(path).resolve())
    cached = _SCORING_WEIGHTS_CACHE.get(resolved_path)
    if cached is not None:
        return dict(cached)

    config_path = Path(path)
    if not config_path.exists():
        _SCORING_WEIGHTS_CACHE[resolved_path] = dict(DEFAULT_WEIGHTS)
        return dict(DEFAULT_WEIGHTS)

    weights = dict(DEFAULT_WEIGHTS)
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key not in DEFAULT_WEIGHTS:
            continue
        try:
            weights[key] = float(value.strip())
        except ValueError:
            continue

    _SCORING_WEIGHTS_CACHE[resolved_path] = dict(weights)
    return weights
