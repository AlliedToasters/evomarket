# Proposal: Trading System

## Change ID
`trading-system`

## Summary
Implement the order book (posted public orders at nodes) and P2P trade proposal system, including order lifecycle management, execution, and settlement.

## Motivation
P2P and public trading is the core social mechanic of the game. It's what makes the economy more than just "harvest and sell to NPCs" — it enables arbitrage, specialization, negotiation, and emergent market dynamics.

## What's Changing

### New Files
- `evomarket/engine/trading.py` — Order book, P2P trades, settlement
- `tests/test_trading.py`

### Data Models

**PostedOrder:**
- `order_id: str` (unique, generated)
- `poster_id: str` (agent who posted)
- `node_id: str` (where the order is posted)
- `side: BuySell` (BUY or SELL)
- `commodity: CommodityType`
- `quantity: int`
- `price_per_unit: float`
- `status: OrderStatus` (ACTIVE, SUSPENDED, FILLED, CANCELLED)
- `created_tick: int`

**TradeProposal:**
- `trade_id: str` (unique, generated)
- `proposer_id: str`
- `target_id: str`
- `node_id: str` (must both be at this node)
- `offer: dict[str, int | float]` (commodity/credit amounts offered)
- `request: dict[str, int | float]` (commodity/credit amounts requested)
- `status: TradeStatus` (PENDING, ACCEPTED, REJECTED, EXPIRED, INVALID)
- `created_tick: int`

### Order Book Operations

`post_order(world: WorldState, agent_id: str, order: PostOrderAction) -> PostedOrder`
- Validate agent has funds/inventory to cover the order
- Check agent is under max_open_orders limit
- Create order with ACTIVE status at agent's current node
- For sell orders: do NOT escrow inventory (agent keeps items until filled)
- For buy orders: do NOT escrow credits (checked at fill time)

`accept_order(world: WorldState, agent_id: str, order_id: str) -> TradeResult`
- Verify order exists, is ACTIVE, and is at agent's node
- Verify acceptor has required funds/inventory
- Verify poster still has required funds/inventory (may have changed since posting)
- If poster can't cover: order is cancelled, acceptor's action fails
- If both can cover: execute the trade atomically
- Transfer commodities and credits between agents
- Mark order as FILLED (or partially filled if we support that — start with fill-or-nothing)
- Verify invariant

`cancel_order(world: WorldState, agent_id: str, order_id: str) -> bool`
- Free action — only the poster can cancel their own orders
- Mark as CANCELLED

`suspend_orders_for_agent(world: WorldState, agent_id: str, node_id: str) -> None`
- Called when agent moves away from a node
- All their ACTIVE orders at that node become SUSPENDED

`reactivate_orders_for_agent(world: WorldState, agent_id: str, node_id: str) -> None`
- Called when agent arrives at a node
- All their SUSPENDED orders at that node become ACTIVE

### P2P Trade Operations

`propose_trade(world: WorldState, proposer_id: str, proposal: ProposeTradeAction) -> TradeProposal`
- Verify both agents are at the same node
- Verify proposer has the offered items
- Check proposer is under max_pending_trades limit
- Create proposal with PENDING status
- Proposal is delivered to target at start of next tick (one-tick latency like messages)

`accept_trade(world: WorldState, agent_id: str, trade_id: str) -> TradeResult`
- Verify proposal exists, is PENDING, and agent is the target
- Verify both agents are still at the same node
- Verify both agents still have the required items
- Execute trade atomically — swap all items and credits
- Verify invariant

`expire_pending_trades(world: WorldState, max_age: int) -> list[str]`
- Called during tick cleanup
- Expire proposals older than max_age ticks
- Return list of expired trade IDs

### TradeResult
- `success: bool`
- `trade_type: Literal["order", "p2p"]`
- `buyer_id: str`
- `seller_id: str`
- `items_transferred: dict` (what moved and in which direction)
- `credits_transferred: float`
- `failure_reason: str | None`

### Trade History

`get_trade_history(world: WorldState, node_id: str, limit: int) -> list[TradeResult]`
- Returns recent completed trades at a node
- Used by agents to assess market conditions and reputation

### Death Cleanup

`cancel_all_orders_for_agent(world: WorldState, agent_id: str) -> None`
- Cancel all posted orders and pending proposals for a dead agent
- Called during DEATH phase

## Acceptance Criteria
- Orders are only visible/fillable at their posted node
- Orders suspend when poster leaves node, reactivate on return
- Insufficient funds at fill time correctly cancels the order
- P2P trades require same-node co-location for both proposal and acceptance
- All trades preserve the fixed-supply invariant
- Dead agent cleanup removes all their orders and proposals
- No partial fills (fill-or-nothing for v1)
- Trade history is queryable by node
- Property-based test: random sequences of post/accept/cancel never violate invariant

## Dependencies
- `core-data-models`
- `action-system` (for action types, but can develop in parallel using shared type definitions)

## Estimated Complexity
High. ~500-700 lines of trading code, ~600-800 lines of tests (many edge cases around timing and insufficient funds).
