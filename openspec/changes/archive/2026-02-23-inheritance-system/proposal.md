## Why

The inheritance system is the mechanism that returns credits to circulation when agents die, which is critical for the fixed-supply economy. Without it, agent death is undefined — credits would vanish, violating the core invariant. It also creates strategic depth: agents can form alliances, use wills as negotiation leverage, and influence wealth concentration dynamics.

## What Changes

- New `evomarket/engine/inheritance.py` module implementing will management, death resolution, and estate distribution
- New `tests/test_inheritance.py` with comprehensive edge-case and property-based testing
- Will updates become an agent action (validated during VALIDATE, applied during RESOLVE)
- Death resolution executes during the DEATH tick phase for agents with balance ≤ 0 after tax
- Estate distribution: will-based transfers to living beneficiaries, unclaimed portions split between local agents and treasury, unclaimed commodities destroyed

## Capabilities

### New Capabilities
- `inheritance`: Will management, death resolution, estate distribution — the complete lifecycle of agent death and wealth redistribution

### Modified Capabilities
_(none — no existing specs to modify)_

## Impact

- **Code**: New `engine/inheritance.py` module; future integration points with `engine/tick.py` (DEATH phase), `engine/trading.py` (order cancellation on death), `engine/communication.py` (message cleanup on death)
- **Models**: `Agent.will` field already exists on the core model; `Agent.alive` flag already exists. No model changes needed.
- **Invariant**: All death operations must preserve `sum(agent_balances) + sum(npc_budgets) + treasury = TOTAL_SUPPLY`. Credits flow agent→beneficiaries and agent→treasury. Commodities are either transferred or destroyed (never created).
- **Dependencies**: Trading and communication systems not yet implemented — will use stubs/interfaces for order and message cleanup callbacks.
