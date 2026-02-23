## ADDED Requirements

### Requirement: CommodityType enum
The system SHALL define a `CommodityType` enum with values: `IRON`, `WOOD`, `STONE`, `HERBS`.

#### Scenario: All commodity types available
- **WHEN** the `CommodityType` enum is accessed
- **THEN** it contains exactly `IRON`, `WOOD`, `STONE`, and `HERBS`

### Requirement: Fixed-supply invariant
The system SHALL enforce that `sum(agent_balances) + sum(npc_budgets) + treasury = TOTAL_SUPPLY` at all times, where all values are integer millicredits. `WorldState` SHALL provide a `verify_invariant()` method that asserts exact integer equality (`==`).

#### Scenario: Invariant holds after world generation
- **WHEN** `generate_world(config, seed)` creates a new world
- **THEN** `verify_invariant()` passes

#### Scenario: Invariant holds after credit transfer
- **WHEN** `transfer_credits()` moves credits between any two reservoirs
- **THEN** `verify_invariant()` passes immediately after

#### Scenario: Invariant violation detected
- **WHEN** an agent's credits are directly mutated (bypassing `transfer_credits()`) to create a 1-millicredit discrepancy
- **THEN** `verify_invariant()` raises an `AssertionError`

### Requirement: Atomic credit transfer
The system SHALL provide a `transfer_credits(from_id, to_id, amount)` method on `WorldState` that atomically moves integer millicredits between any two reservoirs. The `amount` parameter is an `int` (millicredits). Reservoirs are identified as: an agent ID (agent balance), a node ID (NPC budget), or `"treasury"`. The method SHALL raise an error if the source has insufficient funds, leaving all balances unchanged.

#### Scenario: Transfer from agent to agent
- **WHEN** `transfer_credits("agent_001", "agent_002", 10_000)` is called and agent_001 has ≥ 10000 millicredits
- **THEN** agent_001's credits decrease by 10000 and agent_002's credits increase by 10000

#### Scenario: Transfer from agent to treasury
- **WHEN** `transfer_credits("agent_001", "treasury", 5_000)` is called
- **THEN** agent_001's credits decrease by 5000 and treasury increases by 5000

#### Scenario: Transfer from treasury to NPC budget
- **WHEN** `transfer_credits("treasury", "node_iron_peak", 20_000)` is called
- **THEN** treasury decreases by 20000 and node_iron_peak's `npc_budget` increases by 20000

#### Scenario: Transfer from NPC budget to agent
- **WHEN** `transfer_credits("node_iron_peak", "agent_001", 5_000)` is called and the node has ≥ 5000 millicredits budget
- **THEN** node_iron_peak's `npc_budget` decreases by 5000 and agent_001's credits increase by 5000

#### Scenario: Insufficient funds
- **WHEN** `transfer_credits("agent_001", "agent_002", 100_000)` is called and agent_001 has only 30000 millicredits
- **THEN** an error is raised and no balances change

#### Scenario: Zero-amount transfer
- **WHEN** `transfer_credits("agent_001", "agent_002", 0)` is called
- **THEN** no balances change and no error is raised

### Requirement: Supply-responsive NPC pricing
The system SHALL provide a `get_npc_price(node_id, commodity)` method on `WorldState` that returns the current NPC buy price in millicredits as an `int`, using the formula: `base_price * (capacity - stockpile) // capacity` (integer floor division). This ensures no fractional millicredits are produced.

#### Scenario: Price at zero stockpile
- **WHEN** `get_npc_price(node_id, commodity)` is called and the NPC stockpile for that commodity is 0
- **THEN** the returned price equals `npc_base_prices[commodity]` in millicredits (full price)

#### Scenario: Price at full stockpile
- **WHEN** `get_npc_price(node_id, commodity)` is called and the NPC stockpile equals `npc_stockpile_capacity`
- **THEN** the returned price equals 0

#### Scenario: Price at half stockpile
- **WHEN** `get_npc_price(node_id, commodity)` is called and the NPC stockpile is exactly half of capacity
- **THEN** the returned price equals `base_price // 2` in millicredits (floor division)

#### Scenario: Commodity not bought at node
- **WHEN** `get_npc_price(node_id, commodity)` is called for a commodity not in the node's `npc_buys` list
- **THEN** the returned price equals 0 (NPC does not buy this commodity here)

### Requirement: Treasury model
The `WorldState` SHALL hold a `treasury: int` representing unclaimed millicredits. The treasury is initialized during world generation with `total_credit_supply` minus all millicredits allocated to agents and NPC budgets.

#### Scenario: Treasury initialized correctly
- **WHEN** a world is generated with `total_credit_supply=10_000_000` millicredits (10000 display credits), 20 agents at 30_000 millicredits each, and NPC budgets totaling 1_000_000 millicredits
- **THEN** treasury equals `10_000_000 - (20 * 30_000) - 1_000_000 = 8_400_000`

#### Scenario: Treasury non-negative after generation
- **WHEN** a world is generated with any valid config
- **THEN** treasury is ≥ 0

### Requirement: WorldState tick counter
The `WorldState` SHALL maintain a `tick: int` counter starting at 0, representing the current simulation tick.

#### Scenario: Initial tick is zero
- **WHEN** a world is generated
- **THEN** `world_state.tick` equals 0

### Requirement: WorldState agent counter
The `WorldState` SHALL maintain a `next_agent_id: int` counter for generating unique agent IDs. It SHALL increment after each agent creation and never decrement.

#### Scenario: Counter increments on agent creation
- **WHEN** the world is generated with 20 agents
- **THEN** `next_agent_id` equals 20

#### Scenario: Counter never decreases
- **WHEN** an agent dies
- **THEN** `next_agent_id` does not change

### Requirement: WorldState JSON checkpointing
The `WorldState` SHALL support serialization to JSON (including RNG state) and deserialization back to an identical state. The RNG state SHALL be saved via `random.getstate()` and restored via `random.setstate()`.

#### Scenario: Checkpoint round-trip
- **WHEN** a `WorldState` is serialized to JSON and deserialized back
- **THEN** the resulting state is functionally identical (same nodes, agents, treasury, tick, and RNG produces the same next values)
