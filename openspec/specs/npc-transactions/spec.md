## ADDED Requirements

### Requirement: NPC buy transaction processing
The system SHALL provide a `process_npc_sell(world: WorldState, agent_id: str, commodity: CommodityType, quantity: int) -> NpcTransactionResult` function that processes an agent selling commodities to the NPC at the agent's current node. The function SHALL calculate price per unit iteratively — each unit sold increases the NPC stockpile by 1 before the next unit's price is computed, preventing bulk sales at peak price. The function SHALL use `transfer_credits()` for all credit movements and SHALL preserve the fixed-supply invariant.

#### Scenario: Single unit sale at zero stockpile
- **WHEN** an agent at a node with zero NPC stockpile for IRON sells 1 unit of IRON, and the node buys IRON with base_price=5000mc and capacity=50
- **THEN** the agent receives 5000mc (full base price), the node's NPC stockpile for IRON increases to 1, the agent's IRON inventory decreases by 1, and the node's NPC budget decreases by 5000mc

#### Scenario: Multi-unit iterative pricing
- **WHEN** an agent sells 3 units of IRON at a node with zero stockpile, base_price=5000mc, capacity=50
- **THEN** unit 1 price is `5000 * (50-0) // 50 = 5000`, unit 2 price is `5000 * (50-1) // 50 = 4900`, unit 3 price is `5000 * (50-2) // 50 = 4800`, and the total payout is 14700mc

#### Scenario: Budget-constrained sale
- **WHEN** an agent sells 5 units but the node's NPC budget can only cover 3 units worth of credits
- **THEN** only 3 units are sold, the agent receives credits equal to the sum of prices for 3 units, `units_sold` is 3, and the remaining 2 units stay in the agent's inventory

#### Scenario: Commodity not bought at node
- **WHEN** an agent tries to sell a commodity that is not in the node's `npc_buys` list
- **THEN** the function returns an `NpcTransactionResult` with `units_sold=0` and `total_credits_received=0`

#### Scenario: Agent has insufficient inventory
- **WHEN** an agent has 2 units of IRON but tries to sell 5
- **THEN** only 2 units are sold and the result reflects the actual quantity transacted

#### Scenario: Invariant preserved after transaction
- **WHEN** any `process_npc_sell()` call completes
- **THEN** `world.verify_invariant()` passes

### Requirement: NPC transaction result type
The system SHALL define an `NpcTransactionResult` dataclass with fields: `units_sold: int`, `total_credits_received: Millicredits`, `price_per_unit: list[Millicredits]` (price paid for each unit, showing the price curve), and `remaining_budget: Millicredits` (node's NPC budget after transaction).

#### Scenario: Result reflects iterative pricing
- **WHEN** an agent sells 3 units with decreasing prices
- **THEN** `price_per_unit` is a list of 3 values in descending order, and `total_credits_received` equals their sum

### Requirement: Bulk NPC price query
The system SHALL provide a `get_npc_prices(world: WorldState, node_id: str) -> dict[CommodityType, Millicredits]` function that returns the current NPC buy price for every commodity at the specified node. Commodities not bought at the node SHALL be omitted from the result.

#### Scenario: Trade hub with all commodities
- **WHEN** `get_npc_prices()` is called on a trade hub that buys all 4 commodity types
- **THEN** the result contains 4 entries, each matching `world.get_npc_price(node_id, commodity)`

#### Scenario: Resource node with single commodity
- **WHEN** `get_npc_prices()` is called on a resource node that only buys IRON
- **THEN** the result contains only `{CommodityType.IRON: <price>}`
