# Strategy Interface Specification

All strategies must implement the following contract.

## Lifecycle Methods

### initialize(context)

Called once before simulation begins.

Context may include:

- Initial capital
- Configuration parameters
- Instrument metadata

---

### on_candle(candle)

Called for every new market data point.

Input:

candle:
timestamp
open
high
low
close
volume

### generate_orders()

Returns a list of orders to execute.

Order structure:
order:
side: BUY | SELL
quantity: float
order_type: MARKET

Limit orders are not required in V1.

---

### on_fill(fill)

Called when an order is executed.

Provides execution details.

---

### finalize()

Called after simulation ends.

May return custom statistics.

---

## Constraints

- Strategies must not access external APIs
- No global mutable state
- Deterministic behavior required for identical inputs
