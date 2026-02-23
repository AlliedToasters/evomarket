### Requirement: Agents can post buy and sell orders at their current node
The system SHALL allow an agent to post a buy or sell order for a commodity at their current node. The order SHALL specify commodity type, quantity (int), and price per unit (Millicredits). The order SHALL be created with ACTIVE status. The system SHALL reject the order if the agent already has `max_open_orders` active or suspended orders.

#### Scenario: Successful sell order posting
- **WHEN** an agent at node_hub_iron posts a sell order for 5 IRON at 3000 mc/unit
- **THEN** a PostedOrder is created with status ACTIVE, side SELL, at node_hub_iron, and the agent's inventory is unchanged (no escrow)

#### Scenario: Successful buy order posting
- **WHEN** an agent at node_hub_iron posts a buy order for 3 WOOD at 4000 mc/unit
- **THEN** a PostedOrder is created with status ACTIVE, side BUY, at node_hub_iron, and the agent's credits are unchanged (no escrow)

#### Scenario: Order rejected due to limit
- **WHEN** an agent with 5 existing orders (active + suspended) posts a new order
- **THEN** the order is rejected and no order is created

### Requirement: Orders are only visible and fillable at their posted node
The system SHALL restrict order visibility and fillability to the node where the order was posted. An agent MUST be at the same node as an order to accept it.

#### Scenario: Agent accepts order at same node
- **WHEN** an agent at node_hub_iron attempts to accept an ACTIVE order posted at node_hub_iron
- **THEN** the acceptance is processed (subject to validation)

#### Scenario: Agent cannot accept order at different node
- **WHEN** an agent at node_hub_wood attempts to accept an order posted at node_hub_iron
- **THEN** the acceptance is rejected

### Requirement: Orders suspend when poster leaves node and reactivate on return
The system SHALL set all ACTIVE orders for an agent at a node to SUSPENDED when that agent leaves the node. The system SHALL set all SUSPENDED orders for an agent at a node to ACTIVE when that agent arrives at the node.

#### Scenario: Orders suspend on departure
- **WHEN** agent_001 has 2 ACTIVE orders at node_hub_iron and moves to node_hub_wood
- **THEN** both orders at node_hub_iron become SUSPENDED

#### Scenario: Orders reactivate on arrival
- **WHEN** agent_001 arrives at node_hub_iron where they have 2 SUSPENDED orders
- **THEN** both orders become ACTIVE

#### Scenario: Suspended orders cannot be accepted
- **WHEN** an agent at node_hub_iron attempts to accept a SUSPENDED order
- **THEN** the acceptance is rejected

### Requirement: Agents can cancel their own orders
The system SHALL allow an agent to cancel their own orders. Only the order poster can cancel. Cancelled orders MUST NOT be fillable.

#### Scenario: Poster cancels own order
- **WHEN** agent_001 cancels their own ACTIVE order
- **THEN** the order status becomes CANCELLED

#### Scenario: Non-poster cannot cancel order
- **WHEN** agent_002 attempts to cancel an order posted by agent_001
- **THEN** the cancellation is rejected

### Requirement: Accepting an order validates both parties can cover the trade
The system SHALL verify at fill time that the poster still has the required inventory (for sells) or credits (for buys), and that the acceptor has the required credits (for sells) or inventory (for buys). If the poster cannot cover, the order SHALL be cancelled and the acceptance fails. Fill-or-nothing: the full quantity must be available.

#### Scenario: Both parties can cover — trade executes
- **WHEN** agent_001 has a sell order for 5 IRON at 3000 mc and agent_002 (with 15000 mc) accepts
- **THEN** 5 IRON transfers from agent_001 to agent_002, 15000 mc transfers from agent_002 to agent_001, and the order becomes FILLED

#### Scenario: Poster no longer has inventory — order cancelled
- **WHEN** agent_001 posted a sell order for 5 IRON but now has only 2 IRON, and agent_002 accepts
- **THEN** the order is cancelled, agent_002's action fails with reason "poster cannot cover", and no items or credits move

#### Scenario: Acceptor has insufficient credits
- **WHEN** agent_002 with 5000 mc attempts to accept a sell order for 5 IRON at 3000 mc (total: 15000 mc)
- **THEN** the acceptance fails with reason "acceptor cannot cover", and the order remains ACTIVE
