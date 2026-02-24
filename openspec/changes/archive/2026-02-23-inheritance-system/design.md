## Context

EvoMarket uses a fixed credit supply where credits circulate between agent balances, NPC node budgets, and the world treasury. When agents die (balance ≤ 0 after tax), their estate (credits + inventory) must be distributed without violating the supply invariant. The `Agent` model already has a `will: dict[str, float]` field and `alive: bool` flag. The `WorldState` provides `transfer_credits()` for atomic credit moves and `verify_invariant()` for validation. No engine modules exist yet — inheritance is the first.

## Goals / Non-Goals

**Goals:**
- Implement will management (update, read) with full validation
- Implement death resolution that distributes estate per will, then splits unclaimed remainder between local agents and treasury
- Handle batch deaths deterministically (agent_id order)
- Preserve the fixed-supply invariant through all operations
- Provide clean integration points for future trading/communication cleanup

**Non-Goals:**
- Implementing the DEATH tick phase orchestration (that's `engine/tick.py`)
- Order cancellation or message cleanup (stubs only — trading/communication systems don't exist yet)
- Agent respawning (that's `engine/spawning.py`)
- Will-related agent actions or prompt integration (Phase 1 concern)

## Decisions

### 1. Direct commodity distribution (not liquidation)

**Decision**: Beneficiaries receive commodities directly as fractional shares (rounded down per commodity type). Unclaimed commodities are destroyed.

**Rationale**: Forced liquidation at NPC prices would create artificial price pressure and unfairly disadvantage estates with large commodity holdings. Direct distribution is simpler, more strategic (beneficiaries can choose when to sell), and avoids coupling to the NPC pricing system.

**Alternative considered**: Liquidate at average NPC prices across all nodes. Rejected — adds complexity, couples systems, and removes strategic choice from beneficiaries.

### 2. Death processing order: sorted agent_id

**Decision**: When multiple agents die in the same tick, process deaths in `agent_id` lexicographic order.

**Rationale**: Determinism requires a fixed ordering. Agent ID order is simple, predictable, and doesn't introduce bias based on game state. An agent who dies later in the processing order can still receive from an earlier-processed will (they're alive when the earlier death resolves).

**Alternative considered**: Randomized order using world RNG. Rejected — harder to reason about and debug, minimal gameplay benefit.

### 3. Credits use Millicredits (int), commodities use int — no float division

**Decision**: Credit distribution uses integer millicredits with floor division. Commodity distribution uses integer floor division per type. Any remainder (from rounding) stays in the unclaimed pool.

**Rationale**: The system already uses `Millicredits = int` throughout. Integer arithmetic avoids float precision issues and makes invariant verification exact. Rounding remainders into the unclaimed pool (which flows to treasury/local agents) ensures no credits are lost.

### 4. Callback stubs for cross-system cleanup

**Decision**: `resolve_death` accepts optional callback functions `cancel_orders_fn` and `clear_messages_fn` with default no-op implementations. These will be replaced with real implementations when trading and communication systems are built.

**Rationale**: Avoids import coupling to modules that don't exist yet while establishing the integration contract. The callback signature is the interface.

### 5. Result objects as plain Pydantic models

**Decision**: `WillUpdateResult`, `WillTransfer`, and `DeathResult` are Pydantic `BaseModel` subclasses with `frozen=True`.

**Rationale**: Consistent with the codebase pattern (Agent, Node are Pydantic models). Frozen results prevent accidental mutation. Pydantic provides free serialization for logging/analysis.

## Risks / Trade-offs

**[Risk] Rounding can lose small credit amounts** → Remainders flow to unclaimed pool, then to treasury/local agents. The invariant check catches any leakage. With millicredit precision, rounding loss is at most N-1 millicredits per distribution (where N = number of beneficiaries).

**[Risk] Batch death ordering creates asymmetry** → Agent A processed before Agent B means A's beneficiaries receive before B dies. This is intentional and documented — it creates interesting edge cases without adding complexity. The ordering is deterministic and predictable.

**[Risk] Dead beneficiaries in will waste estate** → By design. Agents should maintain their wills. A will naming only dead agents results in 100% unclaimed distribution. This creates strategic pressure to update wills.
