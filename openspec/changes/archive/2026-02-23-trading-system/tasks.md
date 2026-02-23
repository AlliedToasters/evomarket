## 1. Data Models

- [x] 1.1 Define enums: BuySell (BUY, SELL), OrderStatus (ACTIVE, SUSPENDED, FILLED, CANCELLED), TradeStatus (PENDING, ACCEPTED, REJECTED, EXPIRED, INVALID)
- [x] 1.2 Define PostedOrder Pydantic model (order_id, poster_id, node_id, side, commodity, quantity, price_per_unit as Millicredits, status, created_tick)
- [x] 1.3 Define TradeProposal Pydantic model (trade_id, proposer_id, target_id, node_id, offer commodities dict, offer_credits, request commodities dict, request_credits, status, created_tick)
- [x] 1.4 Define TradeResult dataclass (success, trade_type, buyer_id, seller_id, items_transferred, credits_transferred, failure_reason, tick)
- [x] 1.5 Add order_book (dict[str, PostedOrder]), trade_proposals (dict[str, TradeProposal]), trade_history (list[TradeResult]), and next_order_seq (int) to WorldState

## 2. Order Book Operations

- [x] 2.1 Implement post_order(): validate agent location, check max_open_orders limit, create ACTIVE order with deterministic ID (order_{tick}_{seq})
- [x] 2.2 Implement cancel_order(): verify poster ownership, set status to CANCELLED
- [x] 2.3 Implement accept_order(): verify same-node co-location, verify order is ACTIVE, validate poster can cover, validate acceptor can cover, execute trade or cancel/fail
- [x] 2.4 Implement suspend_orders_for_agent(): set all ACTIVE orders at a node to SUSPENDED when agent departs
- [x] 2.5 Implement reactivate_orders_for_agent(): set all SUSPENDED orders at a node to ACTIVE when agent arrives

## 3. P2P Trade Operations

- [x] 3.1 Implement propose_trade(): verify co-location, verify proposer has offered items/credits, check max_pending_trades limit, create PENDING proposal with deterministic ID
- [x] 3.2 Implement accept_trade(): verify target is acceptor, verify co-location still holds, verify both parties have required items/credits, execute trade or set INVALID
- [x] 3.3 Implement reject_trade(): verify target is rejector, set status to REJECTED
- [x] 3.4 Implement expire_pending_trades(): expire proposals older than max_age ticks, return list of expired IDs

## 4. Settlement and History

- [x] 4.1 Implement settle_trade() helper: atomically transfer credits via WorldState.transfer_credits() and commodities via inventory mutation, call verify_invariant(), record TradeResult
- [x] 4.2 Implement get_trade_history(): return recent completed trades at a node, most recent first, with limit parameter
- [x] 4.3 Implement cancel_all_orders_for_agent(): cancel all orders and invalidate all proposals for a dead agent (DEATH phase cleanup)

## 5. WorldState Integration

- [x] 5.1 Update WorldState.__init__() with new fields (order_book, trade_proposals, trade_history, next_order_seq) with defaults
- [x] 5.2 Update WorldState.to_json() and from_json() to serialize/deserialize trading state
- [x] 5.3 Add helper methods on WorldState: orders_at_node(), orders_for_agent(), pending_proposals_for_agent()

## 6. Tests

- [x] 6.1 Test post_order: successful post, limit enforcement, correct status and node assignment
- [x] 6.2 Test accept_order: successful fill, poster can't cover (cancel), acceptor can't cover (fail), wrong node, suspended order rejection
- [x] 6.3 Test cancel_order: poster cancels, non-poster rejected
- [x] 6.4 Test suspend/reactivate: orders suspend on departure, reactivate on arrival
- [x] 6.5 Test propose_trade: successful proposal, not co-located, insufficient items, pending limit
- [x] 6.6 Test accept_trade: successful acceptance, not co-located anymore, proposer lacks items, target rejects
- [x] 6.7 Test expire_pending_trades: correct expiration, not-yet-expired preserved
- [x] 6.8 Test P2P multi-item swaps: pure commodity, commodity-for-credits, mixed, empty rejected
- [x] 6.9 Test settle_trade: credits and commodities transfer correctly, invariant holds
- [x] 6.10 Test trade_history: queryable by node, limit respected, most recent first
- [x] 6.11 Test cancel_all_orders_for_agent: dead agent cleanup of orders and proposals
- [x] 6.12 Property-based test: random sequences of post/accept/cancel/propose/accept never violate the fixed-supply invariant
- [x] 6.13 Test WorldState serialization round-trip with trading state
