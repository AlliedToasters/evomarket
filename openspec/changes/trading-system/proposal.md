## Why

Agents currently have no way to trade with each other — the only economic interaction is selling commodities to NPC nodes. Without player-to-player trading, there's no arbitrage, specialization, negotiation, or emergent market dynamics. The trading system is the core social mechanic that makes EvoMarket more than a solo harvesting game.

## What Changes

- Add **posted order book** at each node: agents post public buy/sell orders for commodities at a price, other co-located agents can fill them
- Add **P2P trade proposals**: agents propose direct multi-item swaps to specific co-located agents, who accept or reject
- Add **order lifecycle management**: orders suspend when poster leaves node, reactivate on return, cancel on death
- Add **trade settlement**: atomic transfer of credits and commodities between agents, with invariant verification
- Add **trade history**: queryable log of completed trades per node (for agent decision-making)
- Add **death cleanup**: cancel all orders and proposals for dead agents

## Capabilities

### New Capabilities
- `order-book`: Public posted orders (buy/sell) at nodes — posting, accepting, cancelling, suspend/reactivate lifecycle, fill-or-nothing execution
- `p2p-trading`: Direct trade proposals between co-located agents — propose, accept, reject, expire, multi-item swaps
- `trade-settlement`: Atomic execution of trades with credit/commodity transfer and invariant verification

### Modified Capabilities
_(none — no existing specs)_

## Impact

- **New file:** `evomarket/engine/trading.py` — all trading logic
- **New file:** `tests/test_trading.py` — comprehensive edge-case tests
- **Models:** New Pydantic models (PostedOrder, TradeProposal, TradeResult) — likely in trading.py or a new models file
- **WorldState:** Will need to store order books and pending proposals (new fields or companion data structure)
- **Dependencies:** Depends on core data models (Agent, Node, WorldState, CommodityType, Millicredits). Uses `WorldState.transfer_credits()` for settlement and `verify_invariant()` for correctness.
- **Config:** Leverages existing `WorldConfig.max_open_orders` (5) and `max_pending_trades` (3)
