## ADDED Requirements

### Requirement: generate_observations returns per-agent observations
`generate_observations(world: WorldState) -> dict[str, AgentObservation]` SHALL return one `AgentObservation` for each living agent, keyed by agent_id.

#### Scenario: Observations generated for all living agents
- **WHEN** world has 18 living agents and 2 dead agents
- **THEN** `generate_observations` returns a dict with 18 entries

#### Scenario: Dead agents receive no observation
- **WHEN** an agent has `alive=False`
- **THEN** no observation is generated for that agent

### Requirement: AgentObservation contains agent state view
Each `AgentObservation` SHALL include an `agent_state` field containing the agent's location, credits, inventory, age, and grace_ticks_remaining.

#### Scenario: Agent state view reflects current state
- **WHEN** an agent has credits=15000, location="node_iron_0", age=5
- **THEN** observation.agent_state shows credits=15000, location="node_iron_0", age=5

### Requirement: AgentObservation contains node info
Each `AgentObservation` SHALL include a `node_info` field with the agent's current node name, type, adjacent node IDs, NPC buy prices for commodities at that node, and resource availability (floor of stockpile for each commodity).

#### Scenario: Node info shows NPC prices
- **WHEN** an agent is at a trade hub with iron NPC price 4200mc
- **THEN** observation.node_info.npc_prices includes IRON: 4200

#### Scenario: Resource availability shows harvestable amounts
- **WHEN** an agent is at a resource node with iron stockpile 3.7
- **THEN** observation.node_info.resource_availability shows IRON: 3

### Requirement: AgentObservation contains agents present
Each `AgentObservation` SHALL include an `agents_present` list of other living agents at the same node, showing agent_id, display_name, and age.

#### Scenario: Agents at same node are visible
- **WHEN** agents A, B, C are at the same node
- **THEN** A's observation.agents_present contains entries for B and C (not A)

### Requirement: AgentObservation contains posted orders
Each `AgentObservation` SHALL include a `posted_orders` list of all active orders at the agent's current node, showing order_id, poster_id, side, commodity, quantity, and price_per_unit.

#### Scenario: Active orders at node are visible
- **WHEN** 3 active orders and 1 suspended order exist at the agent's node
- **THEN** observation.posted_orders contains 3 entries (excluding suspended)

### Requirement: AgentObservation contains received messages
Each `AgentObservation` SHALL include a `messages_received` list of messages delivered to the agent this tick (from the RECEIVE phase).

#### Scenario: Delivered messages appear in observation
- **WHEN** 2 messages were delivered to the agent this tick
- **THEN** observation.messages_received contains 2 entries

### Requirement: AgentObservation contains pending trade proposals
Each `AgentObservation` SHALL include a `pending_proposals` list of trade proposals where the agent is the target, showing trade_id, proposer_id, offered items, and requested items.

#### Scenario: Incoming trade proposal visible
- **WHEN** agent B has proposed a trade to agent A
- **THEN** A's observation.pending_proposals contains the proposal details

### Requirement: AgentObservation contains own orders and proposals
Each `AgentObservation` SHALL include `own_orders` (all non-terminal orders posted by the agent across all nodes) and `own_pending_proposals` (outgoing trade proposals the agent has made).

#### Scenario: Agent sees own orders across nodes
- **WHEN** agent has 2 active orders at different nodes
- **THEN** observation.own_orders contains both orders

### Requirement: AgentObservation contains preamble and prompt document
Each `AgentObservation` SHALL include a `preamble` with tick number, and the agent's `prompt_document` (scratchpad) content.

#### Scenario: Preamble includes current tick
- **WHEN** world.tick is 42
- **THEN** observation.preamble.tick is 42

#### Scenario: Prompt document included
- **WHEN** agent's prompt_document is "my notes"
- **THEN** observation.prompt_document is "my notes"

### Requirement: AgentObservation contains own will
Each `AgentObservation` SHALL include `own_will` showing the agent's current will distribution.

#### Scenario: Will distribution included
- **WHEN** agent's will is {"agent_001": 0.5, "agent_002": 0.3}
- **THEN** observation.own_will is {"agent_001": 0.5, "agent_002": 0.3}
