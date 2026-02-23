## Context

EvoMarket agents currently interact only with NPC nodes (selling commodities for credits). There is no agent-to-agent trading. The core data models (WorldState, Agent, Node, CommodityType, Millicredits) are implemented and stable. WorldConfig already defines `max_open_orders` (5) and `max_pending_trades` (3) in anticipation of this system.

All credit values use the `Millicredits` (int) type — 1000 mc = 1 display credit. `WorldState.transfer_credits()` provides atomic credit movement between agent/NPC/treasury reservoirs with invariant preservation.

## Goals / Non-Goals

**Goals:**
- Implement a node-local order book for public buy/sell orders
- Implement direct P2P multi-item trade proposals between co-located agents
- Atomic settlement that preserves the fixed-supply invariant
- Order lifecycle management (suspend on leave, reactivate on arrive, cancel on death)
- Queryable trade history per node
- Fill-or-nothing execution (no partial fills)

**Non-Goals:**
- Cross-node orders or global order book
- Partial order fills (v2 consideration)
- Automated market makers or algorithmic pricing
- Credit escrow on order posting (too restrictive for Phase 0 exploration)
- Auction mechanics
- NPC-to-agent trade orders (NPCs only operate via existing `get_npc_price` mechanism)

## Decisions

### 1. Trading state lives on WorldState, not on individual Nodes

**Decision:** Add `order_book: dict[str, PostedOrder]` and `trade_proposals: dict[str, TradeProposal]` as top-level attributes on `WorldState`.

**Rationale:** Orders need global lookup by ID (for accept/cancel), per-agent queries (for limits and death cleanup), and per-node queries (for display and matching). A flat dict on WorldState with index helpers is simpler than scattering orders across Node objects. Node-scoped views are derived via filtering on `node_id`.

**Alternative considered:** Storing orders on Node. Rejected because it makes agent-scoped queries (limit checks, death cleanup) require scanning all nodes.

### 2. No credit/inventory escrow on posting

**Decision:** When an agent posts a sell order, items remain in their inventory. When posting a buy order, credits remain in their balance. Availability is checked at fill time.

**Rationale:** Matches the proposal spec. Simplifies posting logic and avoids complex escrow accounting. The trade-off is that orders can become unfillable if the poster spends their resources, but this is handled gracefully — the order is cancelled and the acceptor's action fails with a clear reason.

**Alternative considered:** Escrowing items/credits at post time. Rejected because it adds a third "limbo" reservoir that complicates the invariant and makes the system harder to reason about.

### 3. Prices in Millicredits (int), not float

**Decision:** `PostedOrder.price_per_unit` uses `Millicredits` (int), consistent with all other credit values in the system.

**Rationale:** The existing codebase uses integer millicredits everywhere. Mixing in float prices would create rounding errors and invariant risks. The proposal mentions `float` but this is corrected to match the established convention.

### 4. P2P trade offers use commodity quantities (int) and credit amounts (Millicredits)

**Decision:** `TradeProposal.offer` and `request` are typed as `dict[CommodityType, int]` for commodities plus a separate `offer_credits: Millicredits` and `request_credits: Millicredits` field, rather than a mixed dict.

**Rationale:** Separate typed fields are safer than a mixed `dict[str, int | float]`. This avoids ambiguity about whether a key is a commodity or "credits", and makes validation straightforward with Pydantic.

### 5. Order ID generation uses WorldState RNG

**Decision:** Order and trade IDs are generated as `order_{tick}_{seq}` and `trade_{tick}_{seq}` using a counter, ensuring deterministic IDs.

**Rationale:** The simulation must be deterministic given a fixed seed. UUID generation would break reproducibility. A tick+sequence counter is simple, unique, and debuggable.

### 6. Trade settlement uses existing `transfer_credits()` for credits, direct inventory mutation for items

**Decision:** Credit transfers go through `WorldState.transfer_credits()`. Commodity transfers directly mutate `Agent.inventory` dicts. The settlement function calls `verify_invariant()` after each trade.

**Rationale:** `transfer_credits()` already handles the atomic credit movement with balance checking. Commodity transfers don't affect the credit invariant, so direct mutation is fine. Inventory non-negativity is enforced by pre-validation before settlement.

### 7. All trading functions are pure functions operating on WorldState

**Decision:** Functions like `post_order()`, `accept_order()`, `propose_trade()` take `WorldState` as the first argument and mutate it in place. They return result objects describing what happened.

**Rationale:** Matches the existing engine pattern (WorldState is the mutable root). No need for a Trading service class — stateless functions are simpler and easier to test.

## Risks / Trade-offs

- **[No escrow] Stale orders** — An agent may post a sell order, then sell the items to an NPC before another agent tries to fill the order. → **Mitigation:** Fill-time validation cancels the order and returns a clear failure reason. Agents learn from failed attempts.

- **[Fill-or-nothing] Large orders may never fill** — If an agent posts an order for 10 items but no one has 10 at once, it sits forever. → **Mitigation:** Acceptable for v1. Agents can post smaller orders. Partial fills are a v2 feature.

- **[Node-local only] Limits arbitrage opportunity** — Agents must physically travel to a node to interact with its orders. → **Mitigation:** This is intentional — travel cost creates arbitrage opportunity, which is a core gameplay mechanic.

- **[WorldState growing] Memory with trade history** — Completed trades accumulate. → **Mitigation:** Trade history is capped per node (configurable limit). Old entries are evicted FIFO.
