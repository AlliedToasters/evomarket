## Context

The core data models (Agent, Node, WorldState, CommodityType) are implemented and tested. The next layer is the action system — the interface between agent decisions and the simulation engine. Each tick, every living agent submits one action; the engine validates and resolves all actions simultaneously, then mutates world state accordingly.

The action system must:
- Define all possible agent actions as typed Pydantic models
- Validate each action against current world state
- Resolve conflicts deterministically when multiple agents compete for scarce resources
- Preserve the fixed-supply invariant through all mutations
- Integrate cleanly with the tick engine's phase pipeline

## Goals / Non-Goals

**Goals:**
- Define a complete, typed action vocabulary covering all agent behaviors
- Implement validation that catches all invalid actions before resolution
- Implement deterministic conflict resolution using the world RNG
- Produce structured ActionResult objects for logging and agent feedback
- Keep the action module self-contained with a clean public API (`validate_action`, `resolve_actions`)

**Non-Goals:**
- Order book persistence or lifecycle (belongs in `engine/trading.py`)
- P2P trade proposal storage and state machine (belongs in `engine/trading.py`)
- Message delivery and storage (belongs in `engine/communication.py`)
- Tick phase orchestration (belongs in `engine/tick.py`)
- Agent decision-making logic (belongs in `agents/`)

## Decisions

### 1. Action types as a sealed Pydantic discriminated union

**Decision:** Define each action as a Pydantic model with a `Literal` type discriminator field. Combine them into `Action = Annotated[Union[...], Discriminator("action_type")]`.

**Rationale:** Pydantic's discriminated unions give us exhaustive type checking, automatic JSON serialization, and clean pattern matching via `match action.action_type`. Alternatives considered:
- *Enum + dataclass:* Less validation, manual serialization
- *Dict-based actions:* No type safety, error-prone

### 2. Two-phase process: validate then resolve

**Decision:** Separate validation from resolution. `validate_action()` checks preconditions and returns the action or replaces it with IdleAction. `resolve_actions()` takes a dict of already-validated actions and resolves conflicts.

**Rationale:** Clean separation of concerns. Validation can run in parallel (per-agent); resolution must be sequential for conflict-sensitive actions. The tick engine calls validate in the VALIDATE phase and resolve in the RESOLVE phase.

### 3. RNG-based priority ordering for conflicts

**Decision:** At the start of each resolution, shuffle agent IDs using `world.rng.sample()` to produce a priority ordering. Conflict-sensitive actions (Harvest, AcceptOrder) resolve in priority order.

**Rationale:** Deterministic given the world RNG seed. Fair over many ticks (random each time). Simple to implement and reason about. Alternative considered:
- *First-come-first-served:* Not meaningful in simultaneous-action model
- *Auction/bidding:* Over-complex for Phase 0

### 4. Actions mutate world state directly during resolution

**Decision:** `resolve_actions()` receives a mutable `WorldState` reference and applies mutations (credit transfers, inventory changes, agent movement) inline during resolution. It uses `WorldState.transfer_credits()` for all credit movements to maintain the invariant.

**Rationale:** The WorldState already provides atomic `transfer_credits()` with invariant checking. Building a separate mutation log and applying it afterward adds complexity without benefit at this stage. Alternative considered:
- *Command pattern with deferred application:* More testable but premature abstraction for Phase 0

### 5. Harvest yields integer units, fractional stockpile rounds down

**Decision:** When an agent harvests, they receive `floor(stockpile)` units (up to 1 unit per harvest action). The fractional remainder stays in the node's stockpile.

**Rationale:** Agents hold integer commodity quantities. Fractional stockpile accumulates from `resource_spawn_rate` (0.5/tick). Harvesting takes whole units only, leaving fractions to accumulate.

### 6. TradeOffer/TradeRequest as typed dicts

**Decision:** Represent trade offers and requests as `dict[CommodityType | Literal["credits"], int]` — a mapping from item type to quantity. Credits are included as a pseudo-commodity in trades.

**Rationale:** Flexible enough for any combination of goods-for-goods, goods-for-credits, or credits-for-goods trades. Using the `"credits"` literal key keeps it simple without adding a separate credit field.

## Risks / Trade-offs

- **[Tight coupling to WorldState internals]** → Mitigated by using only public WorldState methods (`transfer_credits`, `agents_at_node`, `adjacent_nodes`, `get_npc_price`). If WorldState API changes, only the action module needs updating.

- **[Inline mutation makes unit testing harder]** → Mitigated by providing factory fixtures for small WorldState instances in tests. The `generate_world()` function with a fixed seed gives reproducible test worlds.

- **[No rollback on partial resolution failure]** → Acceptable for Phase 0. If a bug corrupts state mid-resolution, `verify_invariant()` will catch it immediately. We can add transactional resolution later if needed.

- **[Action type expansion]** → New action types require adding a model, updating the union, adding validation, and adding resolution logic. This is linear work but manageable. A plugin system would be premature.
