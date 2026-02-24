## Why

All subsystems (actions, trading, communication, economy, inheritance) are complete and individually tested, but there is no orchestration layer to drive the simulation. The tick engine is the central integration point that resolves a complete game tick through a strict 10-phase pipeline, enforcing determinism and the fixed-supply invariant.

## What Changes

- Add 10-phase tick resolution pipeline (`execute_tick`) that orchestrates all subsystems in strict order: RECEIVE → OBSERVE → DECIDE → VALIDATE → RESOLVE → TAX → DEATH → SPAWN → REPLENISH → LOG
- Add observation generation system producing structured per-agent views of world state
- Add resource regeneration logic (fractional accumulation per node per tick)
- Add agent spawning logic with location selection and treasury funding
- Add `TickResult` and `TickMetrics` models capturing all per-tick outcomes
- Support debug mode with per-phase invariant checking and hyperfast mode (≥1000 ticks/s)

## Capabilities

### New Capabilities
- `tick-pipeline`: 10-phase tick resolution loop with strict phase ordering, deterministic execution, and invariant enforcement
- `observation-generation`: Structured per-agent observation generation from world state (agent state, node info, orders, messages, proposals, will)
- `resource-regeneration`: Fractional resource spawning per node per tick, capped at resource_cap
- `agent-spawning`: Spawn replacement agents when population drops below target, with location selection and treasury-funded starting credits

### Modified Capabilities
_(none — this change integrates existing capabilities without altering their requirements)_

## Impact

- **New files:** `evomarket/engine/tick.py`, `evomarket/engine/observation.py`, `evomarket/engine/spawning.py`, `tests/test_tick.py`, `tests/test_observation.py`, `tests/test_spawning.py`
- **Dependencies:** Calls into all existing subsystems — actions, trading, communication, economy, inheritance
- **APIs:** Exposes `execute_tick(world, agent_decisions) -> TickResult` as the primary simulation driver
- **Performance:** Must support hyperfast mode (≥1000 ticks/second with 20 heuristic agents)
