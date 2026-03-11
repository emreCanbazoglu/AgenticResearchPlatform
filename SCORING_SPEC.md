# Scoring System Specification

## Raw Performance Metrics

Required metrics:

- Total Return
- Annualized Return (if applicable)
- Number of Trades
- Win Rate

---

## Risk Metrics

Required metrics:

- Maximum Drawdown
- Volatility
- Sharpe Ratio (or simplified equivalent)

---

## Composite Score

A single scalar score used for strategy ranking.

Example weighted formula:

CompositeScore =
w1 _ normalized_return +
w2 _ normalized*sharpe -
w3 * normalized*drawdown +
w4 * normalized_trade_count

Weights defined in config/scoring.yaml.

---

## Requirements

- Metrics must be reproducible
- No randomness
- Same inputs must produce identical scores
