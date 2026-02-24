## Context

The core data models (`evomarket/core/`) are fully implemented with `WorldState`, `Node`, `Agent`, `WorldConfig`, `transfer_credits()`, `get_npc_price()`, and `verify_invariant()`. All credit values use integer millicredits. The NPC economy change builds the operational layer on top of these primitives — the functions that the tick engine will call during RESOLVE, TAX, SPAWN, and REPLENISH phases.

Currently no engine modules exist. This is the first module in `evomarket/engine/`, establishing the pattern for how engine code interacts with `WorldState`.

## Goals / Non-Goals

**Goals:**
- Implement the complete credit circulation loop: agents sell → NPC pays → treasury replenishes NPC → tax returns to treasury
- All credit movements go through `transfer_credits()` so the invariant is enforced automatically
- Iterative per-unit pricing prevents bulk dumping exploits
- Budget constraints create economic scarcity and strategic decisions
- Stockpile decay creates price recovery, preventing permanent price depression
- Clean function signatures that the tick engine can call directly

**Non-Goals:**
- Agent decision-making or action validation (belongs to `action-system`)
- P2P trading between agents (belongs to `trading-system`)
- Tick phase orchestration (belongs to `tick-engine`)
- Agent death or will execution (belongs to `inheritance-system`)
- Dynamic NPC pricing formulas beyond the existing `base_price * (capacity - stockpile) // capacity`

## Decisions

### 1. Single module: `evomarket/engine/economy.py`

**Decision**: All NPC economy functions live in one module with pure functions taking `WorldState` as the first argument. No classes — just functions and result dataclasses.

**Rationale**: These functions are stateless operations on `WorldState`. They don't need their own state, so classes would add indirection without benefit. A single module keeps the economy logic co-located and easy to test.

**Alternative considered**: Separate files per concern (npc_transactions.py, treasury.py, tax.py). Rejected — the functions are tightly related (all operate on the same credit reservoirs) and the total code is ~200-300 lines. Splitting would fragment without adding clarity.

### 2. Result types as frozen dataclasses

**Decision**: `NpcTransactionResult`, `ReplenishResult`, and `TaxResult` are `@dataclass(frozen=True)` classes defined in the same module. Not Pydantic models.

**Rationale**: These are simple return types — they don't need validation, serialization, or schema generation. Frozen dataclasses are lightweight and immutable, signaling that results are read-only snapshots.

**Alternative considered**: Pydantic models for consistency with core models. Rejected — no serialization or validation needed for transient result objects.

### 3. Iterative pricing with early-exit on budget exhaustion

**Decision**: `process_npc_sell()` loops unit-by-unit, computing the price at the current stockpile level before each unit. The loop exits early if: (a) the NPC budget can't cover the next unit's price, (b) the agent has no more inventory, or (c) all requested units are sold. Each unit's credit transfer happens inside the loop via `transfer_credits()`.

**Rationale**: Per-unit `transfer_credits()` calls mean the invariant holds at every step, not just at the end. This is slightly more expensive than batch-computing total price then doing one transfer, but correctness is paramount — and the overhead is negligible (a few integer additions per unit, no I/O).

**Alternative considered**: Compute total price first, then do a single transfer. Faster, but if the budget runs out mid-way, we'd need to reverse-compute partial quantities, making the code more complex and error-prone. The per-unit approach is simpler and naturally handles partial sales.

### 4. Equal distribution is the only replenishment strategy (for now)

**Decision**: `replenish_npc_budgets()` splits the replenishment amount equally across all NPC nodes (nodes with `npc_buys`). The `npc_budget_distribution` config field exists for future extensibility but only `"equal"` is implemented.

**Rationale**: Equal distribution is the simplest correct approach. More sophisticated strategies (proportional to demand, priority to lowest budgets) add complexity without clear benefit until we observe economic dynamics in simulation. The config field allows adding strategies later without API changes.

**Alternative considered**: Proportional to recent sales volume. Better economically, but requires tracking per-node transaction history, which doesn't exist yet.

### 5. Stockpile decay uses integer truncation

**Decision**: Decay is computed as `decay_amount = int(stockpile * decay_rate)`, then `new_stockpile = stockpile - decay_amount`. At low stockpiles (e.g., stockpile=1, rate=0.1), `int(0.1) = 0` so no decay occurs — the stockpile only decays when the computed amount rounds to at least 1.

**Rationale**: Integer math avoids fractional stockpile tracking. The "minimum effective stockpile" behavior is acceptable — very small stockpiles already produce near-maximum prices, so whether they decay by 0 or 1 has negligible economic impact.

**Alternative considered**: Float stockpiles with rounding. Would require changing the Node model's `npc_stockpile` type from `int` to `float`, rippling through pricing and transaction code.

### 6. Tax collection with partial payment

**Decision**: `collect_tax()` takes whatever the agent has if they can't pay the full amount. It uses a single `transfer_credits()` call with `min(amount, agent.credits)`. The `TaxResult.paid_full` field tells the caller whether the agent is solvent.

**Rationale**: The tick engine's DEATH phase uses `paid_full` to determine if an agent should die. Partial collection ensures credits are never lost — even a dying agent's remaining balance goes to the treasury (or to heirs via the inheritance system).

### 7. `fund_spawn()` is a check-and-deduct, not a full spawn

**Decision**: `fund_spawn()` only deducts from the treasury and returns a boolean. It does NOT create an agent or assign credits to the agent. The caller (spawn logic in the tick engine) is responsible for creating the agent and transferring credits from a holding pool or directly crediting the new agent.

**Rationale**: Separating the treasury check from agent creation keeps `fund_spawn()` simple and testable. The spawn phase needs to do many things (pick location, create Agent model, assign ID) that don't belong in the economy module.

**Note**: The deducted credits are temporarily "in transit" — the treasury decreases but no agent receives them yet. The caller MUST complete the spawn by crediting the new agent, or return the credits to the treasury. The invariant will fail if this contract is violated.

## Risks / Trade-offs

**[Per-unit transfer_credits() in process_npc_sell() is O(n) in units sold]** → Mitigation: Acceptable for Phase 0 (small unit quantities, no I/O). If performance matters later, we can batch-compute the total and do a single transfer, but only after validating the batch math handles partial sales correctly.

**[Equal replenishment may starve high-demand nodes]** → Mitigation: Monitor in simulation. If nodes near popular resource areas run out of budget while remote nodes have unused budget, implement proportional or priority-based distribution. The config field is ready.

**[fund_spawn() creates a temporal invariant gap]** → Mitigation: Document clearly that the caller must complete the spawn. Add an assertion in the tick engine's spawn phase to verify the invariant after all spawns complete. The gap is within a single function call, not across ticks.

**[Integer truncation in stockpile decay means very small stockpiles persist]** → Mitigation: Acceptable — small stockpiles already produce near-maximum prices. In practice, stockpiles will fluctuate in ranges where decay is effective (10+). If needed, add a minimum decay of 1 when stockpile > 0.
