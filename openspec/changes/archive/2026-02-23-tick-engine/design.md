## Context

All six subsystems (actions, trading, communication, economy, inheritance, world generation) are implemented and individually tested. The tick engine is the final integration layer — it orchestrates a complete game tick through a 10-phase pipeline, calling into each subsystem in strict order.

The codebase uses millicredits (int) throughout, Pydantic models for data, and a mutable `WorldState` container that holds all game state including RNG. All subsystem functions take `WorldState` as first argument and mutate it in place.

## Goals / Non-Goals

**Goals:**
- Implement the 10-phase tick pipeline with strict ordering guarantees
- Generate structured per-agent observations from world state
- Implement agent spawning with treasury-funded starting credits
- Implement resource regeneration with fractional accumulation
- Capture all tick outcomes in a `TickResult` for logging/analysis
- Support debug mode (per-phase invariant checks) and hyperfast mode (end-of-tick only)
- Maintain determinism: same seed + same agent decisions = identical results

**Non-Goals:**
- Agent implementations (heuristic, LLM, random) — these are separate modules
- Simulation runner / multi-tick loop orchestration — that's `simulation/runner.py`
- Metrics persistence / SQLite logging — that's `simulation/logging.py`
- Text rendering of observations for LLM agents — that's the agent interface's job

## Decisions

### 1. `agent_decisions` callable signature

**Decision:** `agent_decisions: Callable[[dict[str, AgentObservation]], dict[str, AgentTurnResult]]`

The tick engine receives a callable that takes all observations and returns all decisions at once. This allows batch processing (important for LLM agents sharing a context window) and keeps the engine agnostic to agent implementation.

**Alternative considered:** Per-agent callable `(AgentObservation) -> AgentTurnResult`. Simpler interface but prevents batch optimizations and adds per-agent call overhead in hyperfast mode.

### 2. Observation as structured data, not text

**Decision:** `AgentObservation` is a hierarchy of dataclasses/Pydantic models. Text rendering is the agent interface's responsibility.

This keeps the tick engine fast (no string formatting) and allows different agent types to consume observations differently (heuristic agents read fields directly, LLM agents render to text).

### 3. Spawn location selection

**Decision:** New agents spawn at a random SPAWN-type node, selected via `world.rng`. If no SPAWN nodes exist, fall back to any node. One agent per spawn call, up to `max_spawns_per_tick` (default: population_size, to allow full replenishment).

**Alternative considered:** Spawn at lowest-population node. Rejected because it adds complexity and the spawn node type already provides a designated entry point.

### 4. Resource regeneration as a simple accumulation

**Decision:** Each RESOURCE node accumulates `resource_spawn_rate * distribution[commodity]` per tick, capped at `resource_cap`. This lives in `tick.py` as a helper since it's a simple loop (not worth a separate module).

### 5. Trade proposal expiry in RESOLVE phase

**Decision:** Before resolving actions, expire all pending trade proposals from the previous tick. This ensures proposals have a one-tick window for acceptance.

### 6. Grace period handling

**Decision:** Agents with `grace_ticks_remaining > 0` skip tax collection. Grace ticks decrement at the start of the TAX phase (before tax check). This means an agent with 1 grace tick remaining gets taxed on the tick that grace expires.

Correction: Grace ticks decrement during TAX phase. If `grace_ticks_remaining > 0`, decrement and skip tax. If 0, collect tax. This gives exactly `spawn_grace_period` tax-free ticks.

### 7. Age increment timing

**Decision:** Agent ages increment at the end of the tick (LOG phase), after all other phases complete. Age 0 = agent's first tick.

### 8. Death cleanup callbacks

**Decision:** The tick engine passes `cancel_orders_fn` and `clear_messages_fn` to `resolve_deaths()` using lambdas that call into the trading and communication modules. This avoids the inheritance module needing direct imports of those systems.

`cancel_orders_fn` calls `cancel_order()` for each of the dead agent's orders.
`clear_messages_fn` calls `clear_messages_for_agent()`.

## Risks / Trade-offs

**[Performance] Observation generation overhead** → Keep observations as lightweight dataclass views, not deep copies. Profile if hyperfast target is missed.

**[Determinism] RNG consumption order** → The tick engine must consume RNG values in a fixed, documented order. Any change to RNG consumption order changes all downstream results. Risk mitigation: integration tests that assert exact TickResult values for a fixed seed.

**[Invariant] Temporary invariant violation during spawn** → `fund_spawn()` deducts from treasury before the agent exists, briefly violating the invariant. Risk mitigation: agent creation immediately follows funding; invariant check happens after both complete.

**[Complexity] Phase coupling** → TAX produces the dead agent list that DEATH consumes. DEATH produces population count that SPAWN uses. This is by design but means phases can't be reordered. Risk mitigation: the phase enum enforces ordering; tests verify the full pipeline.
