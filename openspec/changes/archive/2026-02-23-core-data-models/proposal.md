## Why

Every system in EvoMarket—tick engine, trading, NPC economy, inheritance, communication—depends on shared data types for agents, nodes, commodities, and currency. These foundational models must be implemented first with the fixed-supply invariant built into the data layer from the start. Without validated core types, parallel development of other subsystems is blocked.

## What Changes

- Define `CommodityType` enum and `NodeType` enum as shared types
- Create `Node` model with resource distribution, NPC pricing/stockpile, adjacency, and budget
- Create `Agent` model with credits, inventory, location, will, grace period, and prompt document
- Create `WorldState` model as the root container holding nodes, agents, treasury, tick counter, and seeded RNG
- Implement `WorldConfig` for parameterizing world generation
- Implement `verify_invariant()` to enforce `sum(agent_balances) + sum(npc_budgets) + treasury = TOTAL_SUPPLY`
- Implement `transfer_credits()` for atomic credit movement between any two reservoirs
- Implement `get_npc_price()` with supply-responsive pricing: `base_price * (1 - stockpile / capacity)`
- Implement `generate_world()` for deterministic, seeded world graph generation with clustered resource regions
- Implement query helpers: `agents_at_node()`, `adjacent_nodes()`
- All models use Pydantic v2 for validation and JSON serialization
- Full test coverage with property-based tests (hypothesis) for economic invariants

## Capabilities

### New Capabilities
- `world-graph`: World graph topology—nodes, edges, adjacency, resource distribution, and deterministic world generation
- `agent-state`: Agent state model—credits, inventory, location, will, prompt document, lifecycle tracking
- `economy-core`: Fixed-supply economy primitives—treasury, NPC budgets, credit transfers, supply-responsive NPC pricing, invariant enforcement

### Modified Capabilities
<!-- No existing specs to modify—this is the foundational change. -->

## Impact

- **New files**: `evomarket/core/types.py`, `evomarket/core/world.py`, `evomarket/core/agent.py`, `evomarket/core/resources.py`, `evomarket/core/economy.py`
- **New tests**: `tests/test_world.py`, `tests/test_agent.py`, `tests/test_economy.py`, `tests/conftest.py`
- **Dependencies**: None—this is the foundation all other changes (action-system, trading, NPC economy, tick engine) build upon
- **APIs**: Establishes the core model interfaces that all engine phases and subsystems will import
- **Invariant**: Introduces the critical fixed-supply assertion that must hold after every state mutation throughout the project
