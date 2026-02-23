# Proposal: Core Data Models

## Change ID
`core-data-models`

## Summary
Define all foundational data models for the game world: nodes, edges, world graph, agents, inventories, commodities, currency, and the world treasury. This is the foundation that all other components depend on and must be implemented first.

## Motivation
Every other component (tick engine, trading, NPC economy, inheritance) depends on shared data types. Establishing these first with clear interfaces prevents integration headaches later and ensures the fixed-supply invariant is built into the data layer from the start.

## What's Changing

### New Files
- `evomarket/core/world.py` — World graph, Node, Edge models
- `evomarket/core/agent.py` — Agent state model
- `evomarket/core/resources.py` — Commodity types, resource node properties
- `evomarket/core/economy.py` — Treasury, NPC node budget, credit flow primitives
- `evomarket/core/types.py` — Shared type aliases, enums, constants
- `tests/test_world.py`
- `tests/test_agent.py`
- `tests/test_economy.py`
- `tests/conftest.py` — Shared fixtures

### Data Models

**CommodityType** — Enum: IRON, WOOD, STONE, HERBS

**Node:**
- `node_id: str`
- `name: str`
- `node_type: NodeType` (RESOURCE, TRADE_HUB, SPAWN)
- `resource_distribution: dict[CommodityType, float]` (weights summing to ≤1.0, remainder = nothing)
- `resource_spawn_rate: float`
- `resource_stockpile: dict[CommodityType, float]` (current harvestable stock, fractional accumulates)
- `resource_cap: int`
- `npc_buys: list[CommodityType]` (which commodities the NPC will buy here)
- `npc_base_prices: dict[CommodityType, float]`
- `npc_stockpile: dict[CommodityType, int]` (how much the NPC has bought — drives price curve)
- `npc_stockpile_capacity: int`
- `npc_budget: float` (credits available for NPC purchases)
- `adjacent_nodes: list[str]` (node_ids)

**Agent:**
- `agent_id: str`
- `display_name: str`
- `location: str` (node_id)
- `credits: float`
- `inventory: dict[CommodityType, int]`
- `age: int` (ticks survived)
- `alive: bool`
- `will: dict[str, float]` (agent_id → percentage)
- `prompt_document: str` (mutable scratchpad)
- `grace_ticks_remaining: int`

**WorldState:**
- `nodes: dict[str, Node]`
- `agents: dict[str, Agent]`
- `treasury: float`
- `total_supply: float` (constant, set at init)
- `tick: int`
- `rng: Random` (seeded)

**Key methods on WorldState:**
- `verify_invariant()` — assert total credits = total_supply. Call after every mutation.
- `transfer_credits(from_id, to_id, amount)` — atomic credit transfer between any two reservoirs (agent, node budget, treasury). Raises on insufficient funds.
- `get_npc_price(node_id, commodity)` — returns `base_price * (1 - stockpile / capacity)`
- `agents_at_node(node_id)` — returns list of living agents at a node
- `adjacent_nodes(node_id)` — returns list of adjacent node IDs

### World Graph Generation
- `generate_world(config: WorldConfig, seed: int) -> WorldState` — builds the graph topology, distributes resources, initializes treasury and NPC budgets
- The generator should create clustered regions with resource specialization connected by trade hub nodes
- Initial credit distribution: a configurable portion goes to treasury, the rest reserved for NPC budgets

### Fixtures
- `small_world` — 5 nodes, 2 commodity types, 5 agents (for unit tests)
- `standard_world` — 15 nodes, 4 commodity types, 20 agents (for integration tests)

## Acceptance Criteria
- All models validate with Pydantic (no invalid states constructible)
- `verify_invariant()` passes after world generation
- `transfer_credits()` is atomic — either succeeds fully or raises, no partial transfers
- World generation is deterministic given a seed
- All models serialize to/from JSON
- `get_npc_price()` returns 0 when stockpile = capacity, base_price when stockpile = 0
- Full test coverage for all models and methods

## Dependencies
None — this is the foundation.

## Estimated Complexity
Medium. ~500-800 lines of model code, ~300-500 lines of tests.
