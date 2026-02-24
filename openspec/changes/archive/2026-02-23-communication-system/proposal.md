## Why

Natural language communication is the core differentiator of EvoMarket from standard multi-agent simulations. Messages enable negotiation, deception, reputation building, and information trading between agents. The infrastructure must be in place before any agent decision-making (heuristic or LLM) can leverage social interaction.

## What Changes

- New `Message` Pydantic model with sender, recipient (targeted or broadcast), node scope, text, and tick-based delivery timing
- New `MessageQueue` container on `WorldState` managing pending and delivered message buffers
- New `SendMessageAction` action type for agents
- Engine functions for sending, delivering (one-tick latency), querying, and pruning messages
- Death cleanup: drop pending/undelivered messages from/to dead agents
- Bounded message history per node (broadcasts) and per agent (private)

## Capabilities

### New Capabilities
- `message-passing`: Agent-to-agent and broadcast message system with one-tick delivery latency, node-local scope, and bounded history

### Modified Capabilities
_(none — no existing specs)_

## Impact

- **New files**: `evomarket/engine/communication.py`, `tests/test_communication.py`
- **Modified files**: `evomarket/core/world.py` (add `MessageQueue` to `WorldState`), `evomarket/core/types.py` or new action types module (add `SendMessageAction`)
- **Tick integration**: RECEIVE phase delivers pending messages; OBSERVE phase exposes them to agents; DEATH phase cleans up dead agent messages
- **No breaking changes** to existing core models or economy invariants — messages carry no credit cost
