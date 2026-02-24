## ADDED Requirements

### Requirement: resolve_actions function signature
The module SHALL export a `resolve_actions(world: WorldState, actions: dict[str, Action]) -> list[ActionResult]` function that resolves all validated actions for a tick and returns results.

#### Scenario: resolve_actions returns one result per agent
- **WHEN** `resolve_actions` is called with actions for 5 agents
- **THEN** exactly 5 ActionResult objects SHALL be returned

### Requirement: Deterministic priority ordering
At the start of each resolution call, `resolve_actions` SHALL generate a priority ordering by shuffling agent IDs using `world.rng`. The same RNG state SHALL produce the same ordering.

#### Scenario: Same RNG seed produces same priority
- **WHEN** `resolve_actions` is called twice with identical world state (same RNG state) and same actions
- **THEN** the results SHALL be identical

### Requirement: Non-conflicting actions resolve independently
MoveAction, SendMessageAction, UpdateWillAction, InspectAction, and IdleAction SHALL resolve independently of priority ordering and other agents' actions.

#### Scenario: Two agents move simultaneously
- **WHEN** agent_001 moves to node_A and agent_002 moves to node_B
- **THEN** both moves SHALL succeed regardless of priority order

#### Scenario: Idle action always succeeds
- **WHEN** an agent submits an IdleAction
- **THEN** the result SHALL have `success=True`

### Requirement: MoveAction resolution
A valid MoveAction SHALL update the agent's `location` to the `target_node`.

#### Scenario: Agent moves to adjacent node
- **WHEN** agent at node_A submits MoveAction to adjacent node_B
- **THEN** agent's location SHALL become node_B and result SHALL have `success=True`

### Requirement: HarvestAction resolution with conflict
When multiple agents harvest the same node, they SHALL resolve in priority order. Each agent receives up to 1 unit of the commodity with the highest stockpile (floor). If stockpile is depleted before all agents harvest, remaining agents get nothing but their action is still consumed.

#### Scenario: Single agent harvests
- **WHEN** one agent harvests a node with 2.5 IRON stockpile
- **THEN** agent gains 1 IRON, node stockpile decreases by 1.0, result has `success=True`

#### Scenario: Multiple agents harvest insufficient stock
- **WHEN** 3 agents harvest a node with floor(stockpile) = 1 for the highest commodity
- **THEN** only the highest-priority agent SHALL receive the resource; the other 2 get `success=False`

#### Scenario: Harvest commodity selection
- **WHEN** a node has IRON=2.5 and WOOD=0.5
- **THEN** the agent SHALL harvest 1 IRON (highest floor stockpile)

### Requirement: PostOrderAction resolution
A valid PostOrderAction SHALL create a new open order at the agent's current node. For sell orders, the offered inventory SHALL be escrowed (deducted from agent inventory). For buy orders, the cost SHALL be escrowed (deducted from agent credits).

#### Scenario: Sell order escrowed
- **WHEN** agent posts a sell order for 5 IRON at 5000
- **THEN** 5 IRON SHALL be deducted from agent inventory and an order SHALL be created

#### Scenario: Buy order escrowed
- **WHEN** agent posts a buy order for 3 IRON at 5000
- **THEN** 15000 millicredits SHALL be deducted from agent credits and an order SHALL be created

### Requirement: AcceptOrderAction resolution with conflict
When multiple agents accept the same order, the highest-priority agent SHALL win. Other agents' actions SHALL fail with `success=False`.

#### Scenario: Single agent accepts order
- **WHEN** one agent accepts a sell order for 5 IRON at 5000 each
- **THEN** agent pays 25000 credits, receives 5 IRON, seller receives credits, result has `success=True`

#### Scenario: Multiple agents accept same order
- **WHEN** two agents accept the same order
- **THEN** the higher-priority agent SHALL succeed and the lower-priority agent SHALL fail

### Requirement: ProposeTradeAction resolution
A valid ProposeTradeAction SHALL create a pending trade proposal. The offered items SHALL be escrowed (deducted from proposer's inventory/credits).

#### Scenario: Trade proposed successfully
- **WHEN** agent proposes trading 5 IRON for 3000 credits to another agent
- **THEN** 5 IRON SHALL be deducted from proposer's inventory and a pending trade SHALL be created

### Requirement: AcceptTradeAction resolution
A valid AcceptTradeAction SHALL execute the trade: the acceptor's requested items are transferred to the proposer, and the escrowed offered items are transferred to the acceptor.

#### Scenario: Trade accepted and executed
- **WHEN** agent accepts a pending trade (5 IRON for 3000 credits)
- **THEN** acceptor receives 5 IRON and pays 3000 credits; proposer receives 3000 credits; result has `success=True`

### Requirement: SendMessageAction resolution
A valid SendMessageAction SHALL enqueue a message for delivery. The message SHALL include sender_id, target, text, and the current tick.

#### Scenario: Broadcast message
- **WHEN** agent sends message with target="all"
- **THEN** message SHALL be queued for all agents at the sender's current node

#### Scenario: Direct message
- **WHEN** agent sends message to a specific agent_id
- **THEN** message SHALL be queued for that specific agent

### Requirement: UpdateWillAction resolution
A valid UpdateWillAction SHALL replace the agent's `will` with the new `distribution`.

#### Scenario: Will updated
- **WHEN** agent updates will to {"agent_001": 0.5, "agent_002": 0.5}
- **THEN** agent's `will` SHALL be `{"agent_001": 0.5, "agent_002": 0.5}` and result has `success=True`

### Requirement: InspectAction resolution
A valid InspectAction SHALL succeed and produce a detail string containing the target agent's public state: credits, inventory, and age.

#### Scenario: Agent inspected
- **WHEN** agent inspects another agent at the same node
- **THEN** result `detail` SHALL contain the target's credits, inventory summary, and age

### Requirement: Fixed-supply invariant preservation
After `resolve_actions` completes, `world.verify_invariant()` SHALL still pass. No resolution logic SHALL create or destroy credits.

#### Scenario: Invariant holds after mixed actions
- **WHEN** a tick resolves a mix of harvests, trades, orders, and moves
- **THEN** `world.verify_invariant()` SHALL not raise

### Requirement: NPC sell resolution
When an agent sells commodities to an NPC (via PostOrderAction targeting the node NPC), the NPC SHALL buy at the supply-responsive price using `world.get_npc_price()`. Credits are transferred from the node's `npc_budget` to the agent.

#### Scenario: NPC buy at current price
- **WHEN** agent sells 1 IRON to NPC at a node where get_npc_price returns 4000
- **THEN** 4000 millicredits SHALL transfer from npc_budget to agent and NPC stockpile increases by 1

#### Scenario: NPC has insufficient budget
- **WHEN** agent tries to sell to NPC but node npc_budget is less than the price
- **THEN** the action SHALL fail with `success=False`
