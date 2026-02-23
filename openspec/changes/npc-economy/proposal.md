## Why

The core data models define NPC budget fields, supply-responsive pricing, and `transfer_credits()`, but no higher-level economy operations exist yet. Agents have no way to sell harvested commodities for credits, the treasury cannot replenish node budgets, and there is no tax collection or spawn funding mechanism. Without these operations, the credit circulation loop (agents harvest → sell to NPC → NPC budgets drain → treasury replenishes → tax returns credits to treasury) cannot function, and no other subsystem can drive meaningful economic activity.

## What Changes

- Add `process_npc_sell()` — iterative, supply-responsive NPC buy transactions with budget capping
- Add `replenish_npc_budgets()` — treasury-to-node budget distribution each tick
- Add `decay_npc_stockpiles()` — stockpile decay so prices recover over time
- Add `collect_tax()` — agent-to-treasury survival tax with graceful handling of insufficient funds
- Add `fund_spawn()` — treasury-to-agent starting endowment for new agent spawns
- Add `get_npc_prices()` — bulk price query for all commodities at a node
- Add result types: `NpcTransactionResult`, `ReplenishResult`, `TaxResult`
- Add configuration parameters: `npc_budget_distribution`, `treasury_min_reserve`

## Capabilities

### New Capabilities
- `npc-transactions`: NPC buy-order processing — iterative pricing, budget-constrained sales, inventory/credit transfers
- `treasury-ops`: Treasury management — budget replenishment, spawn funding, tax collection, stockpile decay

### Modified Capabilities
- `economy-core`: Adding `npc_budget_distribution` and `treasury_min_reserve` to `WorldConfig`

## Impact

- **New files**: `evomarket/engine/economy.py`, `tests/test_engine_economy.py`
- **Modified files**: `evomarket/core/world.py` (add config params to `WorldConfig`)
- **APIs**: All new functions operate on `WorldState` and use `transfer_credits()` for credit movements
- **Dependencies**: Depends only on `core-data-models` (already implemented)
- **Invariant**: Every operation preserves the fixed-supply invariant by using `transfer_credits()` exclusively
- **Downstream consumers**: `tick-engine` (RESOLVE, TAX, DEATH, SPAWN, REPLENISH phases all call these functions)
