## ADDED Requirements

**Cross-reference:** The availability predicates in `observation.py` (`_compute_action_availability`) mirror these validators to pre-compute which actions are available for prompt rendering. Changes to validation logic here should be reflected in the observation availability computation.

### Requirement: validate_action function signature
The module SHALL export a `validate_action(agent_id: str, action: Action, world: WorldState) -> Action` function. It returns the action unchanged if valid, or an `IdleAction` if invalid.

#### Scenario: Valid action passes through
- **WHEN** `validate_action` is called with a valid MoveAction to an adjacent node
- **THEN** the same MoveAction SHALL be returned unchanged

#### Scenario: Invalid action replaced with IdleAction
- **WHEN** `validate_action` is called with an invalid MoveAction to a non-adjacent node
- **THEN** an `IdleAction` SHALL be returned

### Requirement: Invalid actions produce warning logs
When `validate_action` replaces an action with IdleAction, it SHALL log a warning containing the agent_id, the original action type, and the reason for rejection.

#### Scenario: Warning logged for invalid move
- **WHEN** agent_001 submits a MoveAction to non-adjacent node
- **THEN** a warning log SHALL be emitted containing "agent_001", "move", and a reason mentioning adjacency

### Requirement: MoveAction validation
MoveAction SHALL be valid only if `target_node` is in the agent's current node's `adjacent_nodes` list.

#### Scenario: Move to adjacent node is valid
- **WHEN** agent is at node_A and target_node is node_B which is adjacent to node_A
- **THEN** validation SHALL pass

#### Scenario: Move to non-adjacent node is invalid
- **WHEN** agent is at node_A and target_node is node_C which is NOT adjacent to node_A
- **THEN** validation SHALL fail and return IdleAction

#### Scenario: Move to nonexistent node is invalid
- **WHEN** target_node does not exist in the world
- **THEN** validation SHALL fail and return IdleAction

### Requirement: HarvestAction validation
HarvestAction SHALL be valid only if the agent's current node has `node_type == RESOURCE` and at least one commodity in `resource_stockpile` has `floor(quantity) >= 1`.

#### Scenario: Harvest at resource node with stock
- **WHEN** agent is at a RESOURCE node with iron stockpile of 2.5
- **THEN** validation SHALL pass

#### Scenario: Harvest at resource node with zero stock
- **WHEN** agent is at a RESOURCE node with all stockpiles below 1.0
- **THEN** validation SHALL fail and return IdleAction

#### Scenario: Harvest at trade hub
- **WHEN** agent is at a TRADE_HUB node
- **THEN** validation SHALL fail and return IdleAction

### Requirement: PostOrderAction validation
PostOrderAction SHALL be valid only if: for buy orders, the agent has `credits >= quantity * price`; for sell orders, the agent has `inventory[commodity] >= quantity`. Additionally, the agent MUST have fewer than `max_open_orders` existing open orders.

#### Scenario: Valid sell order with sufficient inventory
- **WHEN** agent has 10 IRON and posts a sell order for 5 IRON
- **THEN** validation SHALL pass

#### Scenario: Sell order with insufficient inventory
- **WHEN** agent has 2 IRON and posts a sell order for 5 IRON
- **THEN** validation SHALL fail and return IdleAction

#### Scenario: Valid buy order with sufficient credits
- **WHEN** agent has 50000 millicredits and posts a buy order for 3 IRON at 5000 each
- **THEN** validation SHALL pass

#### Scenario: Buy order with insufficient credits
- **WHEN** agent has 10000 millicredits and posts a buy order for 3 IRON at 5000 each
- **THEN** validation SHALL fail and return IdleAction

### Requirement: AcceptOrderAction validation
AcceptOrderAction SHALL be valid only if: the order exists, is at the agent's current node, and the agent has sufficient credits (to fill a sell order) or inventory (to fill a buy order).

#### Scenario: Valid order acceptance
- **WHEN** a sell order for 5 IRON at 5000 exists at agent's node and agent has 25000 credits
- **THEN** validation SHALL pass

#### Scenario: Order does not exist
- **WHEN** the order_id does not match any open order
- **THEN** validation SHALL fail and return IdleAction

#### Scenario: Order at different node
- **WHEN** the order exists but is at a different node than the agent
- **THEN** validation SHALL fail and return IdleAction

### Requirement: ProposeTradeAction validation
ProposeTradeAction SHALL be valid only if: the target agent exists, is alive, is at the same node, the proposing agent has all offered items in sufficient quantity, and the agent has fewer than `max_pending_trades` pending proposals.

#### Scenario: Valid trade proposal
- **WHEN** both agents are at the same node and proposer has offered items
- **THEN** validation SHALL pass

#### Scenario: Target agent at different node
- **WHEN** target agent is at a different node
- **THEN** validation SHALL fail and return IdleAction

#### Scenario: Insufficient offered items
- **WHEN** proposer offers 5 IRON but only has 3
- **THEN** validation SHALL fail and return IdleAction

#### Scenario: Self-trade proposal
- **WHEN** agent proposes a trade to themselves
- **THEN** validation SHALL fail and return IdleAction

### Requirement: AcceptTradeAction validation
AcceptTradeAction SHALL be valid only if: the trade proposal exists, is pending for this agent, and both parties still have the required items/credits.

#### Scenario: Valid trade acceptance
- **WHEN** trade is pending for this agent and both parties have required items
- **THEN** validation SHALL pass

#### Scenario: Trade not pending for this agent
- **WHEN** trade_id does not correspond to a pending trade for this agent
- **THEN** validation SHALL fail and return IdleAction

### Requirement: SendMessageAction validation
SendMessageAction SHALL be valid only if: the target is `"all"` (broadcast to current node) or a specific agent_id that is alive and at the same node.

#### Scenario: Broadcast message
- **WHEN** target is "all"
- **THEN** validation SHALL pass

#### Scenario: Direct message to co-located agent
- **WHEN** target agent is alive and at the same node
- **THEN** validation SHALL pass

#### Scenario: Direct message to agent at different node
- **WHEN** target agent is at a different node
- **THEN** validation SHALL fail and return IdleAction

### Requirement: UpdateWillAction validation
UpdateWillAction SHALL be valid only if all beneficiary agent IDs reference agents that exist (alive or dead). Will percentages are already validated at model construction time.

#### Scenario: Valid will update
- **WHEN** all beneficiary IDs exist in the world
- **THEN** validation SHALL pass

#### Scenario: Nonexistent beneficiary
- **WHEN** a beneficiary ID does not exist in the world
- **THEN** validation SHALL fail and return IdleAction

### Requirement: InspectAction validation
InspectAction SHALL be valid only if the target agent is alive and at the same node as the inspecting agent.

#### Scenario: Inspect co-located living agent
- **WHEN** target agent is alive and at the same node
- **THEN** validation SHALL pass

#### Scenario: Inspect agent at different node
- **WHEN** target agent is at a different node
- **THEN** validation SHALL fail and return IdleAction

#### Scenario: Inspect dead agent
- **WHEN** target agent is not alive
- **THEN** validation SHALL fail and return IdleAction

### Requirement: IdleAction validation
IdleAction SHALL always be valid.

#### Scenario: Idle is always valid
- **WHEN** validate_action is called with an IdleAction
- **THEN** the IdleAction SHALL be returned unchanged
