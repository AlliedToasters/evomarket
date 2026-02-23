## Context

EvoMarket has no implementation yet—all source modules are empty stubs. This change creates the foundational data layer that every other subsystem imports. The project uses Python 3.12+, Pydantic v2 for model validation/serialization, and pyright in strict mode. The simulation must be deterministic (seeded RNG) and support "hyperfast" mode (≥1000 ticks/second with heuristic agents).

The core data models define three credit reservoirs (agent balances, NPC node budgets, world treasury) that must always sum to `TOTAL_SUPPLY`. This invariant is the single most important correctness property in the system.

## Goals / Non-Goals

**Goals:**
- Establish all foundational types (enums, models, configs) that downstream changes import
- Build the fixed-supply invariant into the data layer so violations are impossible without explicit assertion failures
- Provide deterministic world generation from a seed
- Ensure all models serialize to/from JSON for checkpointing
- Enable fast property-based testing of economic invariants

**Non-Goals:**
- Action validation or resolution (belongs to `action-system`)
- Order book or P2P trade models (belongs to `trading-system`)
- Message passing models (belongs to `communication-system`)
- Tick engine or phase pipeline (belongs to `tick-engine`)
- NPC replenishment logic (belongs to `npc-economy`; we only define the budget field and pricing formula here)
- Agent decision-making interfaces (belongs to `simulation-runner`)

## Decisions

### 1. File organization: five modules in `evomarket/core/`

**Decision**: Split into `types.py` (enums, constants, type aliases), `world.py` (Node, WorldState, world generation), `agent.py` (Agent model), `resources.py` (resource distribution config), `economy.py` (treasury operations, NPC pricing, credit transfer).

**Rationale**: Matches the project architecture in `openspec/project.md`. Keeps each file focused. `types.py` avoids circular imports by holding shared enums/constants that all other modules reference.

**Alternative considered**: Single `models.py` file. Rejected because it would grow large and conflate unrelated concerns.

### 2. Pydantic v2 BaseModel for all data models

**Decision**: Use `pydantic.BaseModel` for `Node`, `Agent`, `WorldConfig`. Use a plain class (not BaseModel) for `WorldState` since it holds a `random.Random` instance which is not directly serializable.

**Rationale**: Pydantic gives us validation, JSON serialization, and immutability options for free. However, `WorldState` needs mutable state and a seeded RNG—Pydantic's `model_config = ConfigDict(arbitrary_types_allowed=True)` would work, but a plain class with explicit `to_json()`/`from_json()` methods gives us cleaner control over RNG serialization (save/restore seed state).

**Alternative considered**: Pydantic for everything with custom serializers for `random.Random`. Viable but adds complexity for marginal benefit.

### 3. Credits as integer millicredits

**Decision**: All credit values (agent balances, NPC budgets, treasury, prices, supply, tax, starting credits) are stored as `int` representing thousandths of a credit (millicredits). 1 display credit = 1000 millicredits. The invariant check uses exact integer equality (`==`). Conversion to display floats happens only at the agent observation layer.

**Rationale**: Integer arithmetic eliminates floating-point drift entirely—the fixed-supply invariant can be checked with `==` instead of epsilon tolerance. NPC pricing (`base_price * (1 - stockpile / capacity)`) uses integer math with explicit rounding (e.g., `base_price * (capacity - stockpile) // capacity`). This is cleaner and safer than epsilon-based checks, especially for long runs in Phase 1+.

**Convention**: Define `Millicredits = int` type alias in `types.py`. Config defaults are expressed in display credits and converted to millicredits at construction (e.g., `total_credit_supply=10_000` → `10_000_000` millicredits). A helper `to_display_credits(mc: int) -> float` converts for the observation layer.

**Alternative considered**: `float` with `math.isclose(abs_tol=1e-9)`. Simpler formulas but introduces drift risk in long simulations and makes the invariant check fuzzy rather than exact.

### 4. `transfer_credits()` as a centralized mutation point

**Decision**: All credit movements go through `WorldState.transfer_credits(from_reservoir, to_reservoir, amount)` where reservoirs are identified by a union type: agent ID, node ID (for NPC budget), or `"treasury"`.

**Rationale**: Centralizing mutations makes the invariant easy to enforce—`transfer_credits` can assert the invariant after every transfer. No code path should directly mutate `agent.credits`, `node.npc_budget`, or `treasury` outside this method.

**Alternative considered**: Per-reservoir deposit/withdraw methods. More granular but harder to guarantee atomicity and invariant checking.

### 5. World generation with clustered topology

**Decision**: `generate_world()` creates a graph by:
1. Creating resource clusters (groups of 2-3 resource nodes with shared commodity specialization)
2. Connecting clusters via trade hub nodes
3. Adding a spawn node connected to a trade hub
4. Building a spanning tree across all nodes first to guarantee connectivity
5. Adding extra intra-cluster and inter-cluster edges for richer topology

The implementation MUST verify connectivity (BFS/DFS from any node reaches all nodes) as a post-condition before returning. A disconnected graph would strand agents with no path to other regions. All randomness flows through a single `random.Random(seed)` instance.

**Rationale**: Building a spanning tree first guarantees connectivity by construction, then layering cluster edges on top gives the desired spatial structure. The connectivity assertion is a safety net against generation bugs.

**Alternative considered**: Random Erdos-Renyi or Watts-Strogatz graphs. Less structured; wouldn't guarantee resource clustering or trade hub placement. Also considered generating edges randomly and retrying on disconnected graphs, but spanning-tree-first is simpler and deterministic without retries.

### 6. Agent IDs are never reused

**Decision**: Agent IDs follow `agent_{zero_padded_number}` format with a monotonically increasing counter on `WorldState`. Dead agent IDs are never reassigned.

**Rationale**: Simplifies will resolution, message history, and event logging—any agent_id uniquely identifies one entity across the entire simulation. Wills referencing dead agents simply skip those entries.

## Risks / Trade-offs

**[Integer rounding in NPC pricing]** → Mitigation: Use consistent rounding (floor division) in `get_npc_price()`. The rounding error is at most 1 millicredit (0.001 display credits) per transaction—negligible at game scale. Document the rounding convention so downstream systems are consistent.

**[WorldState is a god object]** → Mitigation: It's intentionally the single source of truth with controlled mutation through `transfer_credits()`. Downstream systems receive it read-only and return mutation requests (actions). This is the designed architecture per `openspec/project.md`.

**[RNG serialization for checkpointing]** → Mitigation: Save `random.getstate()` in JSON checkpoints, restore with `random.setstate()`. Well-supported in Python stdlib.

**[Node model carries NPC fields even for non-NPC-relevant node types]** → Mitigation: For SPAWN nodes, NPC fields default to empty/zero. The flat model avoids polymorphism complexity. Acceptable at this scale.
