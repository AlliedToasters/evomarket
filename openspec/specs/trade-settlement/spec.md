### Requirement: Trade settlement atomically transfers credits and commodities
The system SHALL execute trades as atomic operations: either all items and credits transfer, or none do. Credit transfers MUST use `WorldState.transfer_credits()`. Commodity transfers MUST directly update agent inventory dicts. The system SHALL call `WorldState.verify_invariant()` after every completed trade.

#### Scenario: Order book trade settlement
- **WHEN** a sell order for 5 IRON at 3000 mc/unit is filled by agent_002
- **THEN** agent_001 loses 5 IRON and gains 15000 mc, agent_002 gains 5 IRON and loses 15000 mc, and the invariant holds

#### Scenario: P2P trade settlement
- **WHEN** a P2P trade of 3 IRON + 2000 mc for 5 HERBS executes
- **THEN** proposer loses 3 IRON and 2000 mc, gains 5 HERBS; target gains 3 IRON and 2000 mc, loses 5 HERBS; and the invariant holds

#### Scenario: Settlement blocked by insufficient funds
- **WHEN** settlement is attempted but one party lacks required credits
- **THEN** no items or credits move, and the trade result indicates failure

### Requirement: All trades preserve the fixed-supply credit invariant
The system SHALL guarantee that `sum(agent_balances) + sum(npc_budgets) + treasury = TOTAL_SUPPLY` holds after every trade. Agent-to-agent trades only move credits between agent reservoirs, so the invariant is preserved by construction. An assertion violation indicates a bug.

#### Scenario: Invariant holds after order book trade
- **WHEN** any order book trade completes
- **THEN** `verify_invariant()` passes

#### Scenario: Invariant holds after P2P trade
- **WHEN** any P2P trade completes
- **THEN** `verify_invariant()` passes

#### Scenario: Random trade sequences preserve invariant
- **WHEN** a random sequence of post/accept/cancel/propose/accept operations is applied
- **THEN** `verify_invariant()` passes after every operation

### Requirement: Trade results are recorded and queryable by node
The system SHALL record all completed trades (both order book and P2P) in a per-node trade history. The history SHALL be queryable with a limit parameter. History entries SHALL include: trade type, buyer/seller IDs, items and credits transferred, and the tick when the trade occurred.

#### Scenario: Query recent trades at a node
- **WHEN** `get_trade_history(world, "node_hub_iron", limit=10)` is called after 3 trades at that node
- **THEN** all 3 trade results are returned, most recent first

#### Scenario: History respects limit
- **WHEN** 20 trades have occurred at a node and `get_trade_history` is called with limit=5
- **THEN** only the 5 most recent trades are returned

### Requirement: Dead agent cleanup removes all orders and proposals
The system SHALL cancel all ACTIVE and SUSPENDED orders for an agent when they die. The system SHALL set all PENDING proposals involving the agent (as proposer or target) to INVALID. This cleanup MUST be callable during the DEATH phase.

#### Scenario: Dead agent's orders are cancelled
- **WHEN** agent_001 dies with 3 active orders and 1 suspended order
- **THEN** all 4 orders become CANCELLED

#### Scenario: Dead agent's proposals are invalidated
- **WHEN** agent_001 dies with 2 pending proposals (1 as proposer, 1 as target)
- **THEN** both proposals become INVALID

### Requirement: Trade results report success, parties, and transferred items
The system SHALL return a TradeResult for every trade attempt. The result SHALL include: success boolean, trade type ("order" or "p2p"), buyer and seller IDs, a dict of items transferred, the credit amount transferred, and a failure reason (None on success).

#### Scenario: Successful trade result
- **WHEN** an order book sell of 5 IRON at 3000 mc/unit completes
- **THEN** the result has success=True, trade_type="order", seller=poster, buyer=acceptor, credits_transferred=15000, items_transferred={IRON: 5}, failure_reason=None

#### Scenario: Failed trade result
- **WHEN** an order acceptance fails due to insufficient funds
- **THEN** the result has success=False and failure_reason describes the issue
