# Proposal: NPC Economy

## Change ID
`npc-economy`

## Summary
Implement the NPC buy-order system, supply-responsive pricing, treasury management, and the credit circulation loop that makes the fixed-supply economy function.

## Motivation
Without the NPC economy, agents have no way to convert harvested commodities into credits. This component is the economic engine that drives the entire game — it creates the incentive to harvest, trade, and move between nodes.

## What's Changing

### New Files
- `evomarket/engine/economy.py` — NPC transaction processing, treasury operations, budget replenishment
- `tests/test_economy.py`

### NPC Buy Transaction

`process_npc_sell(world: WorldState, agent_id: str, commodity: CommodityType, quantity: int) -> NpcTransactionResult`

When an agent sells a commodity to the NPC at their current node:
1. Verify the node's NPC buys this commodity type
2. Calculate current price: `price = base_price * (1 - stockpile / capacity)` per unit
3. For multiple units, price is calculated per-unit iteratively (each unit sold increases stockpile, lowering the next unit's price). This prevents agents from dumping large quantities at the peak price.
4. Calculate total payout. Cap at node's available NPC budget.
5. Transfer credits from node NPC budget to agent balance
6. Increase node's NPC stockpile for that commodity
7. Remove commodity from agent inventory
8. Verify invariant

**NpcTransactionResult:**
- `units_sold: int` (may be less than requested if budget insufficient)
- `total_credits_received: float`
- `price_per_unit: list[float]` (price for each unit, showing the curve)
- `remaining_budget: float`

### Treasury Operations

`replenish_npc_budgets(world: WorldState) -> ReplenishResult`

Called during the REPLENISH tick phase:
1. Calculate total replenishment budget available from treasury
2. Distribute to node NPC budgets proportionally (or equally, configurable)
3. Nodes with lower budgets may get priority (to prevent starvation)
4. Transfer credits from treasury to node budgets
5. Verify invariant

`fund_spawn(world: WorldState, amount: float) -> bool`

Called during SPAWN phase to provide starting endowment:
1. Check treasury has sufficient credits
2. Deduct from treasury
3. Return True if funded, False if treasury insufficient (spawn delayed)

`collect_tax(world: WorldState, agent_id: str, amount: float) -> TaxResult`

Called during TAX phase:
1. Deduct credits from agent balance
2. Add credits to treasury
3. If agent has insufficient credits, take whatever they have (balance → 0)
4. Return result including whether agent can survive

### NPC Stockpile Decay

`decay_npc_stockpiles(world: WorldState) -> None`

Called during REPLENISH phase. NPC stockpiles gradually decay (the NPC "consumes" or "exports" what it bought), which allows prices to recover over time. Without this, NPC prices would only ever decrease.

- Decay rate: configurable per node (e.g., 10% of stockpile per tick)
- Stockpile cannot go below 0

### Price Query

`get_npc_prices(world: WorldState, node_id: str) -> dict[CommodityType, float]`

Returns current NPC buy prices for all commodities at a node. Used by the agent observation system to show agents what they'd get for selling.

### Configuration Additions

| Parameter | Description | Default |
|---|---|---|
| `npc_budget_replenish_rate` | Total credits/tick from treasury to NPC budgets | 5.0 |
| `npc_budget_distribution` | How to split replenishment across nodes | "equal" |
| `npc_stockpile_decay_rate` | Fraction of stockpile that decays per tick | 0.1 |
| `treasury_min_reserve` | Minimum treasury balance (won't replenish below this) | 100 |

## Acceptance Criteria
- Supply-responsive pricing follows the formula exactly
- Multi-unit sales calculate price iteratively (not at a single price point)
- Budget-constrained sales correctly cap at available budget
- Replenishment distributes credits from treasury to nodes without violating invariant
- Stockpile decay allows price recovery over time
- Tax collection always transfers credits to treasury
- All operations preserve the fixed-supply invariant
- Property-based test: run 1000 random NPC transactions, verify invariant holds after each

## Dependencies
- `core-data-models`

## Estimated Complexity
Medium. ~300-400 lines of economy code, ~400-500 lines of tests.
