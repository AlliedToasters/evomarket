## ADDED Requirements

### Requirement: Node types
The system SHALL define a `NodeType` enum with values: `RESOURCE`, `TRADE_HUB`, `SPAWN`.

#### Scenario: All node types are available
- **WHEN** the `NodeType` enum is accessed
- **THEN** it contains exactly `RESOURCE`, `TRADE_HUB`, and `SPAWN`

### Requirement: Node model
The system SHALL define a `Node` Pydantic model with the following fields:
- `node_id: str` — unique identifier (format: `node_{name}`)
- `name: str` — human-readable name
- `node_type: NodeType`
- `resource_distribution: dict[CommodityType, float]` — weights summing to ≤ 1.0
- `resource_spawn_rate: float` — units per tick (fractional accumulates)
- `resource_stockpile: dict[CommodityType, float]` — current harvestable stock
- `resource_cap: int` — maximum stockpile before spawning stops
- `npc_buys: list[CommodityType]` — commodities the NPC buys at this node
- `npc_base_prices: dict[CommodityType, int]` — base prices in millicredits
- `npc_stockpile: dict[CommodityType, int]` — NPC purchased quantity per commodity
- `npc_stockpile_capacity: int`
- `npc_budget: int` — millicredits available for NPC purchases
- `adjacent_nodes: list[str]` — node_ids of connected nodes

#### Scenario: Valid node construction
- **WHEN** a `Node` is constructed with valid fields
- **THEN** the model validates successfully and all fields are accessible

#### Scenario: Resource distribution validation
- **WHEN** a `Node` is constructed with `resource_distribution` weights summing to greater than 1.0
- **THEN** a validation error is raised

#### Scenario: Node JSON serialization
- **WHEN** a `Node` is serialized to JSON and deserialized back
- **THEN** the resulting `Node` is equal to the original

### Requirement: Node adjacency
The system SHALL provide a method `adjacent_nodes(node_id)` on `WorldState` that returns the list of node IDs adjacent to the given node.

#### Scenario: Query adjacent nodes
- **WHEN** `adjacent_nodes(node_id)` is called for a node with 3 neighbors
- **THEN** a list of exactly 3 node IDs is returned

#### Scenario: Adjacency is symmetric
- **WHEN** node A lists node B as adjacent
- **THEN** node B also lists node A as adjacent

### Requirement: World graph connectivity
The system SHALL ensure the generated world graph is fully connected—every node is reachable from every other node via adjacent edges.

#### Scenario: All nodes reachable
- **WHEN** a world is generated with any valid config and seed
- **THEN** a breadth-first search from any node visits all nodes in the graph

### Requirement: Deterministic world generation
The system SHALL provide a `generate_world(config, seed)` function that produces an identical `WorldState` given the same `WorldConfig` and seed value. All randomness SHALL flow through a single `random.Random(seed)` instance.

#### Scenario: Same seed produces same world
- **WHEN** `generate_world(config, seed=42)` is called twice
- **THEN** both calls produce identical node graphs, resource distributions, agent placements, and initial credit allocations

#### Scenario: Different seeds produce different worlds
- **WHEN** `generate_world(config, seed=42)` and `generate_world(config, seed=99)` are called
- **THEN** the resulting worlds differ in topology or resource distribution

### Requirement: Clustered resource topology
The system SHALL generate world graphs with resource clusters—groups of resource nodes sharing a commodity specialization—connected by trade hub nodes.

#### Scenario: Resource nodes cluster by commodity
- **WHEN** a world is generated
- **THEN** resource nodes in the same cluster share a primary commodity type in their `resource_distribution` (weight ≥ 0.5)

#### Scenario: Trade hubs connect clusters
- **WHEN** a world is generated
- **THEN** every trade hub node is adjacent to at least two different resource clusters

### Requirement: WorldConfig model
The system SHALL define a `WorldConfig` Pydantic model containing all configurable world parameters with sensible defaults:
- `num_nodes: int = 15`
- `num_commodity_types: int = 4`
- `total_credit_supply: int = 10_000_000` — millicredits (10,000 display credits)
- `starting_credits: int = 30_000` — millicredits (30 display credits)
- `population_size: int = 20`
- `resource_spawn_rate: float = 0.5`
- `node_resource_cap: int = 20`
- `npc_base_price: int = 5_000` — millicredits (5 display credits)
- `npc_stockpile_capacity: int = 50`
- `npc_budget_replenish_rate: int = 5_000` — millicredits/tick (5 display credits/tick)
- `npc_stockpile_decay_rate: float = 0.1`
- `survival_tax: int = 1_000` — millicredits/tick (1 display credit/tick)
- `spawn_grace_period: int = 5`
- `ticks_per_episode: int = 500`
- `max_open_orders: int = 5`
- `max_pending_trades: int = 3`
- `death_treasury_return_pct: float = 0.5`
- `death_local_share_pct: float = 0.5`

#### Scenario: Default config is valid
- **WHEN** a `WorldConfig` is constructed with no arguments
- **THEN** it uses the default parameter values from the project specification

#### Scenario: Config serialization round-trip
- **WHEN** a `WorldConfig` is serialized to JSON and deserialized back
- **THEN** the resulting config equals the original
