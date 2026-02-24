## ADDED Requirements

### Requirement: RandomAgent baseline
The system SHALL provide a `RandomAgent` that selects a uniformly random valid action each tick. It SHALL filter actions based on current state (no move if no adjacent nodes, no harvest at non-resource nodes, etc.) and never edit the scratchpad.

#### Scenario: Random agent selects valid action
- **WHEN** a `RandomAgent.decide()` is called with any valid observation
- **THEN** the returned action is a valid action type given the agent's current state

#### Scenario: Random agent deterministic with seed
- **WHEN** two `RandomAgent` instances are initialized with the same seed and given the same observation sequence
- **THEN** they produce identical action sequences

### Requirement: HarvesterAgent strategy
The `HarvesterAgent` SHALL follow a harvest-sell loop: move to a resource node, harvest until inventory has items or node is depleted, move to a trade hub, sell to NPC via sell orders, repeat.

#### Scenario: Harvester moves to resource node
- **WHEN** a `HarvesterAgent` is at a non-resource node with no inventory
- **THEN** it moves toward the nearest resource node

#### Scenario: Harvester harvests at resource node
- **WHEN** a `HarvesterAgent` is at a resource node with available resources
- **THEN** it harvests

#### Scenario: Harvester sells at trade hub
- **WHEN** a `HarvesterAgent` is at a trade hub with inventory
- **THEN** it posts sell orders for its commodities

### Requirement: TraderAgent strategy
The `TraderAgent` SHALL exploit spatial price differentials: move between nodes, post buy orders where NPC prices are low (high stockpile), move to nodes where NPC prices are high (low stockpile), and post sell orders.

#### Scenario: Trader buys at cheap node
- **WHEN** a `TraderAgent` observes low NPC prices at its current node and has credits
- **THEN** it posts buy orders for the cheap commodity

#### Scenario: Trader sells at expensive node
- **WHEN** a `TraderAgent` is at a node with high NPC prices and has inventory
- **THEN** it posts sell orders

### Requirement: SocialAgent strategy
The `SocialAgent` SHALL focus on P2P trading: stay at high-traffic nodes, post buy/sell orders, and send trade proposals to co-located agents.

#### Scenario: Social agent proposes trade
- **WHEN** a `SocialAgent` is at a node with other agents and has inventory
- **THEN** it sends trade proposals to co-located agents

#### Scenario: Social agent accepts favorable trades
- **WHEN** a `SocialAgent` receives a trade proposal with a favorable price
- **THEN** it accepts the trade

### Requirement: HoarderAgent strategy
The `HoarderAgent` SHALL accumulate resources and credits, rarely trade, and update its will to name nearby agents as beneficiaries.

#### Scenario: Hoarder harvests and holds
- **WHEN** a `HoarderAgent` has been harvesting
- **THEN** it does not sell unless credits are critically low (near survival tax threshold)

#### Scenario: Hoarder updates will
- **WHEN** a `HoarderAgent` is at a node with other agents
- **THEN** it updates its will to include co-located agents

### Requirement: ExplorerAgent strategy
The `ExplorerAgent` SHALL move frequently across the graph, inspect agents it encounters, and broadcast messages about observed conditions (prices, resources).

#### Scenario: Explorer moves frequently
- **WHEN** an `ExplorerAgent` has been at a node for 1-2 ticks
- **THEN** it moves to an adjacent node

#### Scenario: Explorer inspects and broadcasts
- **WHEN** an `ExplorerAgent` is at a node with other agents
- **THEN** it inspects one agent and broadcasts a message

### Requirement: Heuristic agents use per-agent seeded RNG
Each heuristic agent instance SHALL use a per-agent RNG seeded deterministically from the agent_id, ensuring reproducible behavior across runs.

#### Scenario: Agent RNG is deterministic
- **WHEN** two episodes run with the same seed
- **THEN** each agent makes identical decisions at each tick
