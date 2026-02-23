## ADDED Requirements

### Requirement: Agent model
The system SHALL define an `Agent` Pydantic model with the following fields:
- `agent_id: str` — unique identifier (format: `agent_{zero_padded_number}`, e.g., `agent_042`)
- `display_name: str`
- `location: str` — current node_id
- `credits: int` — current balance in millicredits (1000 = 1 display credit)
- `inventory: dict[CommodityType, int]` — commodity holdings
- `age: int` — ticks survived (starts at 0)
- `alive: bool` — whether the agent is living
- `will: dict[str, float]` — agent_id → percentage mapping
- `prompt_document: str` — mutable scratchpad persisted across ticks
- `grace_ticks_remaining: int` — ticks remaining before survival tax applies

#### Scenario: Valid agent construction
- **WHEN** an `Agent` is constructed with valid fields
- **THEN** the model validates successfully and all fields are accessible

#### Scenario: Agent JSON serialization
- **WHEN** an `Agent` is serialized to JSON and deserialized back
- **THEN** the resulting `Agent` is equal to the original

### Requirement: Agent ID uniqueness
Agent IDs SHALL follow the format `agent_{zero_padded_number}` with a monotonically increasing counter. Dead agent IDs SHALL never be reused.

#### Scenario: Sequential agent IDs
- **WHEN** three agents are created in sequence
- **THEN** they receive IDs `agent_000`, `agent_001`, `agent_002` (or equivalent zero-padded format)

#### Scenario: IDs not reused after death
- **WHEN** `agent_005` dies and a new agent is spawned
- **THEN** the new agent receives `agent_006` (or the next unused number), not `agent_005`

### Requirement: Will validation
The system SHALL validate that will percentages are non-negative and sum to at most 100%.

#### Scenario: Valid will
- **WHEN** an `Agent` is constructed with `will={"agent_001": 0.5, "agent_002": 0.3}`
- **THEN** the model validates successfully (sum = 0.8 ≤ 1.0)

#### Scenario: Will percentages exceed 100%
- **WHEN** an `Agent` is constructed with `will={"agent_001": 0.6, "agent_002": 0.6}`
- **THEN** a validation error is raised (sum = 1.2 > 1.0)

#### Scenario: Negative will percentage
- **WHEN** an `Agent` is constructed with `will={"agent_001": -0.1}`
- **THEN** a validation error is raised

### Requirement: Inventory non-negative
Agent inventory quantities SHALL always be non-negative integers.

#### Scenario: Valid inventory
- **WHEN** an `Agent` is constructed with `inventory={CommodityType.IRON: 5, CommodityType.WOOD: 0}`
- **THEN** the model validates successfully

#### Scenario: Negative inventory rejected
- **WHEN** an `Agent` is constructed with `inventory={CommodityType.IRON: -1}`
- **THEN** a validation error is raised

### Requirement: Credits non-negative at construction
Agent credits SHALL be non-negative at construction time. Credits are stored as `int` millicredits. Credits MAY reach zero or below during gameplay (triggering death in the DEATH tick phase), but the model itself SHALL accept any int value to allow the engine to detect and handle death.

#### Scenario: Agent constructed with positive credits
- **WHEN** an `Agent` is constructed with `credits=30_000` (30 display credits)
- **THEN** the model validates successfully

#### Scenario: Agent with zero credits is valid
- **WHEN** an `Agent` is constructed with `credits=0`
- **THEN** the model validates successfully (death is handled by the engine, not the model)

### Requirement: Agents at node query
The system SHALL provide a method `agents_at_node(node_id)` on `WorldState` that returns a list of all living agents at the given node.

#### Scenario: Query agents at a node
- **WHEN** 3 living agents and 1 dead agent are located at node_id "node_iron_peak"
- **THEN** `agents_at_node("node_iron_peak")` returns a list of exactly 3 agents

#### Scenario: Empty node
- **WHEN** no living agents are at node_id "node_empty"
- **THEN** `agents_at_node("node_empty")` returns an empty list
