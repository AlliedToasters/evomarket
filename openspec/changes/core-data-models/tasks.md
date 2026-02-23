## 1. Shared Types and Constants

- [x] 1.1 Create `evomarket/core/types.py` with `CommodityType` enum (IRON, WOOD, STONE, HERBS), `NodeType` enum (RESOURCE, TRADE_HUB, SPAWN), `Millicredits = int` type alias, `to_display_credits()` helper, and shared type aliases
- [x] 1.2 Create `evomarket/core/__init__.py` re-exporting public types

## 2. Node and World Graph Models

- [x] 2.1 Create `evomarket/core/resources.py` with resource distribution config and validation (weights sum ≤ 1.0)
- [x] 2.2 Create `evomarket/core/world.py` with `Node` Pydantic model (all fields from spec: node_id, name, node_type, resource_distribution, npc fields, adjacency)
- [x] 2.3 Add `WorldConfig` Pydantic model with all configurable parameters and defaults from the project spec

## 3. Agent Model

- [x] 3.1 Create `evomarket/core/agent.py` with `Agent` Pydantic model (agent_id, credits, inventory, location, will, prompt_document, grace_ticks_remaining, alive, age)
- [x] 3.2 Add will validation (percentages ≥ 0, sum ≤ 1.0) and inventory validation (non-negative integers)

## 4. WorldState and Economy Core

- [x] 4.1 Create `evomarket/core/economy.py` with `WorldState` class holding nodes, agents, treasury, tick counter, next_agent_id, total_supply, and seeded RNG
- [x] 4.2 Implement `verify_invariant()` — assert sum(agent_balances) + sum(npc_budgets) + treasury == total_supply using exact integer equality (all values are millicredits)
- [x] 4.3 Implement `transfer_credits(from_id, to_id, amount)` — atomic credit transfer between agent/node/treasury reservoirs with insufficient-funds error
- [x] 4.4 Implement `get_npc_price(node_id, commodity)` — supply-responsive pricing in millicredits: `base_price * (capacity - stockpile) // capacity` (integer floor division), returns 0 for commodities not bought at node
- [x] 4.5 Implement `agents_at_node(node_id)` and `adjacent_nodes(node_id)` query helpers

## 5. World Generation

- [x] 5.1 Implement `generate_world(config, seed)` in `evomarket/core/world.py` — deterministic world graph with clustered resource topology, trade hubs connecting clusters, spawn node
- [x] 5.2 Initialize agents with starting_credits drawn from treasury, placed at spawn nodes
- [x] 5.3 Initialize NPC budgets from treasury allocation; verify invariant after generation

## 6. Serialization

- [x] 6.1 Implement `WorldState.to_json()` and `WorldState.from_json()` with RNG state preservation via `random.getstate()`/`random.setstate()`
- [x] 6.2 Verify all Pydantic models (Node, Agent, WorldConfig) serialize/deserialize via `model_dump_json()`/`model_validate_json()`

## 7. Tests

- [x] 7.1 Create `tests/conftest.py` with `small_world` fixture (5 nodes, 2 commodities, 5 agents) and `standard_world` fixture (15 nodes, 4 commodities, 20 agents)
- [x] 7.2 Create `tests/test_world.py` — node validation, adjacency symmetry, graph connectivity, deterministic generation (same seed = same world), clustered topology
- [x] 7.3 Create `tests/test_agent.py` — agent construction, will validation, inventory validation, ID format and uniqueness
- [x] 7.4 Create `tests/test_economy.py` — invariant enforcement, transfer_credits (all reservoir pairs, insufficient funds, zero amount), NPC pricing (zero/half/full stockpile, non-bought commodity), treasury initialization, checkpoint round-trip
- [x] 7.5 Add hypothesis property-based tests for invariant: verify_invariant holds after arbitrary sequences of transfer_credits calls
