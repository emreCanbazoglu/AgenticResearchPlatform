# System Architecture

## Layered Design

### 1. Market Replay Layer

Simulates market data feed from historical datasets.

Responsibilities:

- Load historical OHLCV data
- Emit time-ordered market events
- Maintain simulated clock
- Provide deterministic playback

No randomness is allowed in this layer.

---

### 2. Strategy Layer

Encapsulates decision logic.

Characteristics:

- Deterministic code
- Stateless or explicitly stateful
- Parameterizable
- Versionable

Strategies do NOT access global state.

---

### 3. Execution Simulator

Acts as a broker substitute.

Responsibilities:

- Accept orders
- Simulate fills
- Apply commission and slippage
- Generate fill events

No order book simulation in V1.

---

### 4. Portfolio Simulator

Tracks account state.

Responsibilities:

- Cash balance
- Open positions
- Equity calculation
- PnL tracking
- Drawdown tracking

---

### 5. Scoring Engine

Evaluates performance after simulation.

Produces:

- Raw metrics
- Risk metrics
- Composite score

Used by meta-controller for selection.

---

### 6. Experiment Runner

Orchestrates a full simulation.

Workflow:

1. Initialize environment
2. Run replay loop
3. Collect results
4. Compute metrics
5. Persist outputs

---

### 7. Meta Controller

Manages strategy lifecycle.

Responsibilities:

- Select top-performing strategies
- Discard weak strategies
- Allocate simulated capital
- Generate parameter variations
- Coordinate experiment batches

AI usage optional.

---

### 8. Persistence Layer

Stores experiment data.

Required stored items:

- Strategy configuration
- Dataset identifier
- Metrics
- Composite score
- Timestamp
- System version

SQLite is sufficient for V1.
