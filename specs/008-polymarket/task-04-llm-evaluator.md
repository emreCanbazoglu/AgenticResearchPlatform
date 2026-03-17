# Task 04 — LLM Evaluator (Probability Estimation)

## Status
Pending

## Owner
Codex agent

## Depends On
- Task 03 — `PolymarketAdapter` and `MarketSnapshot` must exist

## Context

This is the LLM meta-controller layer specific to Polymarket. Unlike the
classical strategies (longshot fade, momentum, mean reversion) which operate
purely on price history, the LLM evaluator reasons about the **content** of
each market — the question text, the category, relevant context — to produce
an independent probability estimate.

The LLM layer runs **once per day**, not on every cycle. It produces a set of
probability estimates for open markets, which the classical adapter then uses
as an additional signal when sizing bets (via the `llm_prior` parameter).

This is optional infrastructure — the adapter must work without it (Task 03),
but with it the system gains a fundamentally different signal source.

## Architecture

```
LLMEvaluator
├── estimate(market_snapshot) → LLMEstimate
│     Calls Claude API with market question + context
│     Returns: estimated_probability, confidence, reasoning
│
├── batch_estimate(snapshots) → list[LLMEstimate]
│     Runs estimates in parallel (up to 5 concurrent)
│     Caches results keyed by (market_id, date) to avoid re-querying
│
├── flag_mispriced(snapshots, threshold=0.10) → list[MispricedMarket]
│     Returns markets where |llm_estimate - market_price| > threshold
│
└── save_estimates(path) / load_estimates(path)
      Persist daily estimates to JSON for audit trail
```

## Data Structures

```python
# domains/polymarket/llm_evaluator.py

@dataclass
class LLMEstimate:
    market_id: str
    question: str
    market_price: float          # current implied probability
    estimated_probability: float # LLM's fair-value estimate
    confidence: float            # 0.0–1.0
    reasoning: str               # LLM's chain-of-thought (1–3 sentences)
    model: str                   # e.g. "claude-3-5-haiku-20241022"
    estimated_at: datetime

@dataclass
class MispricedMarket:
    market_id: str
    question: str
    market_price: float
    llm_estimate: float
    deviation: float             # llm_estimate - market_price (signed)
    direction: str               # "underpriced" | "overpriced"
    confidence: float
    reasoning: str
```

## LLM Prompt Design

### System prompt
```
You are a calibrated probability forecaster specialising in prediction markets.
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
}
```

### User prompt template
```
Market: {question}
Category: {category}
Current market price (implied probability): {current_price:.1%}
Days until resolution: {days_to_resolution:.0f}
Tags: {tags}

Price history (last 10 data points, oldest first):
{price_history_summary}

Estimate the probability this market resolves YES.
```

### Price history summary format
```
{date}: {prob:.0%}  (e.g. "Mar 10: 42%  Mar 11: 45%  Mar 12: 38% ...")
```

## Integration with Adapter

The LLM estimate is injected as an additional parameter `llm_prior` into
the strategy's `parameters` dict:

```python
# In PolymarketAdapter.run_on_snapshots():
if llm_estimates:
    estimate = llm_estimates.get(snapshot.market_id)
    if estimate:
        parameters = {**parameters, "llm_prior": estimate.estimated_probability}
```

Each classical strategy handles `llm_prior` as an optional blend:
```python
# In strategy.evaluate():
llm_prior = parameters.get("llm_prior")
if llm_prior is not None:
    llm_weight = parameters.get("llm_weight", 0.3)  # optimizable
    blended_estimate = llm_weight * llm_prior + (1 - llm_weight) * own_estimate
```

The `llm_weight` parameter (range 0.0–1.0) becomes part of the optimizer
search space, letting the classical optimizer learn how much to trust the LLM
versus its own signal.

## Caching

Daily estimates are cached to avoid redundant API calls:
```
data/polymarket/llm_estimates/
  2026-03-17.json
  2026-03-16.json
  ...
```

Cache key: `(market_id, date)`. If today's estimate exists for a market,
skip the API call and reuse it.

## Cost Management

- Default model: `claude-3-5-haiku-20241022` (fast + cheap)
- Estimated cost: ~$0.001 per market estimate
- 50 open markets per day ≈ $0.05/day
- Hard limit: `max_daily_markets = 100` (configurable)

## Tests

### `tests/unit/test_llm_evaluator.py`

```python
def test_estimate_parses_valid_response(monkeypatch):
    # Mock Claude API response → LLMEstimate fields populated correctly

def test_estimate_handles_malformed_json(monkeypatch):
    # API returns invalid JSON → raises ValueError with clear message

def test_estimate_clamps_probability(monkeypatch):
    # API returns probability=1.5 → clamped to 1.0

def test_flag_mispriced_filters_by_threshold(monkeypatch):
    # 3 markets: deviations 0.05, 0.12, 0.20 with threshold=0.10
    # → returns 2 markets

def test_cache_hit_skips_api_call(monkeypatch, tmp_path):
    # Existing estimate file for today → API never called

def test_batch_estimate_returns_all_results(monkeypatch):
    # 5 snapshots → 5 LLMEstimate objects returned
```

## Acceptance Criteria

- [ ] `domains/polymarket/llm_evaluator.py` implemented
- [ ] Claude API called via `anthropic` SDK (claude-3-5-haiku-20241022)
- [ ] Prompt is structured, chain-of-thought, returns JSON only
- [ ] Daily estimate cache implemented (keyed by market_id + date)
- [ ] `llm_prior` parameter injection into adapter works
- [ ] `llm_weight` is part of the optimizer search space for all 3 strategies
- [ ] `flag_mispriced()` returns sorted list (largest deviation first)
- [ ] All unit tests green (API calls mocked — no real API calls in tests)
- [ ] `uv run pytest` fully green

## Files to Create

- `domains/polymarket/llm_evaluator.py`
- `tests/unit/test_llm_evaluator.py`

## Files to Modify

- `domains/polymarket/adapter.py` — add `llm_estimates` optional param to
  `run_on_snapshots()`
- `domains/polymarket/strategies/*.py` — handle optional `llm_prior` parameter

## Files to NOT Touch

- `domains/trading/`
- `core/`
- `meta/`
- Any existing spec files

## Notes

- This task introduces the first network dependency at runtime (Claude API).
  The `--no-llm` flag on `run_polymarket.py` must bypass this entirely.
- The LLM evaluator is the only component in the platform that makes external
  API calls at evaluation time. Document this clearly in CLAUDE.md.
