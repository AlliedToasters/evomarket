## ADDED Requirements

### Requirement: Will management
The system SHALL allow agents to update their will, replacing the current will entirely. The will is a mapping of beneficiary agent IDs to percentage shares (as floats in [0, 1]). All percentages MUST be non-negative. The total of all percentages MUST NOT exceed 1.0. Beneficiary IDs MUST be valid agent IDs in the world (alive or dead). Percentages that sum to less than 1.0 are valid — the remainder goes to the unclaimed pool on death. The will is public and readable by any agent.

#### Scenario: Valid will update
- **WHEN** an agent updates their will with `{"agent_001": 0.5, "agent_002": 0.3}`
- **THEN** the agent's will is replaced with the new distribution and a successful `WillUpdateResult` is returned

#### Scenario: Will percentages exceed 1.0
- **WHEN** an agent updates their will with `{"agent_001": 0.6, "agent_002": 0.5}`
- **THEN** the update is rejected and the agent's existing will is unchanged

#### Scenario: Negative percentage in will
- **WHEN** an agent updates their will with `{"agent_001": -0.1}`
- **THEN** the update is rejected and the agent's existing will is unchanged

#### Scenario: Will names non-existent agent
- **WHEN** an agent updates their will with `{"nonexistent_agent": 0.5}`
- **THEN** the update is rejected and the agent's existing will is unchanged

#### Scenario: Will names dead agent
- **WHEN** an agent updates their will naming an agent that exists but is dead
- **THEN** the update succeeds — wills MAY name dead agents (the share becomes unclaimed at death resolution)

#### Scenario: Reading another agent's will
- **WHEN** any agent requests the will of another agent
- **THEN** the system returns the target agent's current will distribution

### Requirement: Estate calculation
The system SHALL calculate the total estate of a dying agent as the sum of their credit balance (in millicredits) and all commodity inventory. Credit balance MAY be zero (agent died from tax bringing balance to exactly 0). Commodity quantities are integers.

#### Scenario: Agent dies with credits and inventory
- **WHEN** an agent with 5000 millicredits and {IRON: 3, WOOD: 2} dies
- **THEN** the estate is calculated as 5000 millicredits and {IRON: 3, WOOD: 2}

#### Scenario: Agent dies with zero credits and empty inventory
- **WHEN** an agent with 0 millicredits and all-zero inventory dies
- **THEN** the estate is calculated as 0 millicredits and empty commodities, and distribution is a no-op

### Requirement: Will execution
The system SHALL distribute the estate according to the agent's will. For each beneficiary (processed in will iteration order): if the beneficiary is alive, transfer their percentage of credits (floor division in millicredits) and their percentage of each commodity type (floor division). If the beneficiary is dead, their share becomes unclaimed. The `WillTransfer` result MUST record each beneficiary, the amounts allocated, and whether the transfer succeeded.

#### Scenario: Single living beneficiary at 100%
- **WHEN** an agent dies with will `{"agent_001": 1.0}` and agent_001 is alive, estate is 10000mc and {IRON: 4}
- **THEN** agent_001 receives 10000mc and 4 IRON, unclaimed is 0

#### Scenario: Multiple beneficiaries with partial percentages
- **WHEN** an agent dies with will `{"agent_001": 0.5, "agent_002": 0.3}`, estate is 10000mc and {IRON: 5}
- **THEN** agent_001 receives 5000mc and 2 IRON, agent_002 receives 3000mc and 1 IRON, unclaimed receives 2000mc and 2 IRON

#### Scenario: Beneficiary is dead
- **WHEN** an agent dies with will `{"agent_001": 0.5, "agent_002": 0.5}` and agent_002 is dead
- **THEN** agent_001 receives 5000mc, agent_002's 50% share becomes unclaimed

#### Scenario: All beneficiaries dead
- **WHEN** an agent dies with will naming only dead agents
- **THEN** the entire estate goes to the unclaimed pool

#### Scenario: Empty will
- **WHEN** an agent dies with an empty will `{}`
- **THEN** the entire estate goes to the unclaimed pool

### Requirement: Unclaimed estate distribution
The system SHALL split the unclaimed portion of the estate between local agents and the treasury according to `death_local_share_pct` and `death_treasury_return_pct` from `WorldConfig`. Credits in the local share are divided equally (floor division) among all living agents at the same node as the deceased. Credits in the treasury share are transferred to the world treasury. Unclaimed commodities are destroyed (removed from the game). Any rounding remainders from credit division among local agents go to the treasury.

#### Scenario: Unclaimed credits split between local agents and treasury
- **WHEN** unclaimed credits are 10000mc, `death_local_share_pct=0.5`, `death_treasury_return_pct=0.5`, and 3 living agents are at the deceased's node
- **THEN** local share is 5000mc (each agent gets 1666mc, remainder 2mc goes to treasury), treasury gets 5000mc + 2mc = 5002mc

#### Scenario: No living agents at the deceased's node
- **WHEN** unclaimed credits exist but no living agents are at the deceased's node (all died this tick or node is empty)
- **THEN** the local share portion also goes to the treasury (100% of unclaimed credits go to treasury)

#### Scenario: Unclaimed commodities are destroyed
- **WHEN** unclaimed commodities include {IRON: 3, WOOD: 2}
- **THEN** those commodities are removed from the game and recorded in `DeathResult.commodities_destroyed`

### Requirement: Death cleanup
The system SHALL mark the agent as `alive = False`, invoke the order cancellation callback (if provided) to cancel all posted orders and pending trades, and invoke the message cleanup callback (if provided) to clear pending messages. The agent's will and prompt document remain on the Agent model for archival purposes.

#### Scenario: Agent marked dead after resolution
- **WHEN** death resolution completes for an agent
- **THEN** the agent's `alive` field is `False`

#### Scenario: Cleanup callbacks invoked
- **WHEN** death resolution runs with cancel_orders_fn and clear_messages_fn provided
- **THEN** both callbacks are invoked with the world state and the dead agent's ID

#### Scenario: Cleanup callbacks not provided
- **WHEN** death resolution runs without cleanup callbacks
- **THEN** resolution completes normally (no-op for cleanup steps)

### Requirement: Batch death resolution
The system SHALL process multiple agent deaths in a single tick by iterating through dead agents in lexicographic `agent_id` order. Each death is fully resolved before the next begins. An agent that is a beneficiary in an earlier-processed death receives their inheritance before their own death is processed (if they also die this tick).

#### Scenario: Two agents die, earlier-processed wills earlier-ID agent to later-ID agent
- **WHEN** agent_001 and agent_005 both die this tick, and agent_001's will names agent_005 at 100%
- **THEN** agent_001 is processed first, agent_005 receives agent_001's estate, then agent_005's death is processed (with the inherited estate included in agent_005's estate)

#### Scenario: Two agents die, later-processed wills earlier agent
- **WHEN** agent_001 and agent_005 both die this tick, and agent_005's will names agent_001 at 100%
- **THEN** agent_001 is processed first and marked dead, then agent_005 is processed — agent_001 is dead so the share is unclaimed

#### Scenario: All agents at a node die simultaneously
- **WHEN** all agents at a node die in the same tick
- **THEN** unclaimed local shares have no living recipients and those credits go to treasury instead

### Requirement: Fixed-supply invariant preservation
All death operations MUST preserve the fixed-supply credit invariant: `sum(agent_balances) + sum(npc_budgets) + treasury == total_supply`. Credits flow only between agent balances and treasury — never created or destroyed. Commodities may be destroyed (they are not part of the credit invariant).

#### Scenario: Single death preserves invariant
- **WHEN** a single agent death is resolved
- **THEN** `world.verify_invariant()` passes after resolution

#### Scenario: Batch deaths preserve invariant
- **WHEN** multiple agent deaths are resolved in a single tick
- **THEN** `world.verify_invariant()` passes after all deaths are resolved

#### Scenario: Random death sequences preserve invariant (property-based)
- **WHEN** an arbitrary sequence of deaths with random wills is executed
- **THEN** `world.verify_invariant()` passes after each death resolution
