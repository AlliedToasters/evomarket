## 1. WorldConfig Extension

- [x] 1.1 Add `npc_budget_distribution: str = "equal"` field to `WorldConfig` in `evomarket/core/world.py`
- [x] 1.2 Add `treasury_min_reserve: Millicredits = 100_000` field to `WorldConfig` in `evomarket/core/world.py`

## 2. Result Types and Module Setup

- [x] 2.1 Create `evomarket/engine/__init__.py`
- [x] 2.2 Create `evomarket/engine/economy.py` with `NpcTransactionResult`, `ReplenishResult`, and `TaxResult` as frozen dataclasses

## 3. NPC Transaction Processing

- [x] 3.1 Implement `process_npc_sell(world, agent_id, commodity, quantity) -> NpcTransactionResult` with iterative per-unit pricing, budget capping, and inventory/stockpile updates via `transfer_credits()`
- [x] 3.2 Implement `get_npc_prices(world, node_id) -> dict[CommodityType, Millicredits]` bulk price query

## 4. Treasury Operations

- [x] 4.1 Implement `replenish_npc_budgets(world) -> ReplenishResult` with equal distribution from treasury respecting `treasury_min_reserve`
- [x] 4.2 Implement `decay_npc_stockpiles(world) -> None` with integer truncation decay
- [x] 4.3 Implement `collect_tax(world, agent_id, amount) -> TaxResult` with partial payment handling
- [x] 4.4 Implement `fund_spawn(world, amount) -> bool` treasury check-and-deduct

## 5. Tests

- [x] 5.1 Create `tests/test_engine_economy.py` with tests for `process_npc_sell()`: single unit, multi-unit iterative pricing, budget-constrained sale, commodity not bought, insufficient inventory, invariant preservation
- [x] 5.2 Add tests for `get_npc_prices()`: trade hub with all commodities, resource node with single commodity
- [x] 5.3 Add tests for `replenish_npc_budgets()`: equal distribution, treasury below reserve, treasury at reserve, invariant preservation
- [x] 5.4 Add tests for `decay_npc_stockpiles()`: standard decay, small stockpile, zero stockpile, price recovery after decay
- [x] 5.5 Add tests for `collect_tax()`: sufficient credits, insufficient credits, zero balance, invariant preservation
- [x] 5.6 Add tests for `fund_spawn()`: sufficient treasury, insufficient treasury, invariant preservation
- [x] 5.7 Add hypothesis property-based tests: invariant holds after arbitrary sequences of NPC sells, replenishments, tax collections, and spawn fundings
