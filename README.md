# Agentic Trading Research Platform (V1)

## Purpose

Autonomous experiment platform for discovering, evaluating, and managing trading strategies using historical market replay.

This project is a **research system**, not a production trading system.

Primary goal:

> Reproducible, automated experimentation over strategy space.

---

## Non-Goals

The following are explicitly out of scope for V1:

- Real-money trading
- Broker integrations
- High-frequency trading (HFT)
- Low-latency execution
- News or alternative data ingestion
- Portfolio management across asset classes
- Continuous online learning

---

## Design Principles

- Deterministic execution
- Offline-first (no required APIs)
- Reproducible experiments
- Strategy-agnostic architecture
- Extensible to other decision domains
- Single-developer maintainability

---

## System Overview

The platform simulates trading strategies on historical data using a layered architecture:

1. Market Replay Engine — replays historical data as a live stream
2. Strategy Layer — deterministic decision logic
3. Execution Simulator — fills orders and applies costs
4. Portfolio Simulator — tracks capital and positions
5. Scoring Engine — evaluates performance
6. Experiment Runner — orchestrates simulations
7. Meta Controller — selects and evolves strategies
8. Persistence Layer — stores experiment results

---

## Success Criteria for V1

The system is considered successful if it can:

- Run multiple strategies on historical data
- Produce reproducible results
- Score and compare strategies
- Store experiment outputs
- Support automated batch experimentation

Profitability is NOT a success criterion.

---

## Execution Mode

Primary mode: Historical Replay (Simulated Time)

Real-time data is not required.

---

## Extensibility

The architecture is designed to support future domains such as:

- Game economy optimization
- Pricing strategy simulation
- Resource allocation problems
- Reinforcement learning environments
