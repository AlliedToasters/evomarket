## Context

The EvoMarket engine has a complete 10-phase tick pipeline (`execute_tick`), world generation (`generate_world`), and subsystems for trading, communication, inheritance, and economy. All state lives in `WorldState` with a `WorldConfig` frozen on it. The engine expects an `AgentDecisionsFn` callback that maps `dict[str, AgentObservation] -> dict[str, AgentTurnResult]`.

No simulation orchestrator, agent implementations, metrics collection, event logging, or CLI exist yet. The `evomarket/simulation/` and `evomarket/agents/` packages are empty `__init__.py` stubs.

Credit values throughout the engine use **millicredits** (integers) — `Millicredits = int`. The existing `WorldConfig` already defines all economic parameters. `SimulationConfig` must bridge user-facing "credits" to internal millicredits.

## Goals / Non-Goals

**Goals:**
- Run a complete 500-tick episode with 20 heuristic agents, no crashes, no invariant violations
- Validate that the economy functions: agents survive, trade, die, and wealth distributes non-trivially
- Support "hyperfast" mode at >=1000 ticks/second for parameter tuning
- Log all events to SQLite for post-hoc analysis
- Deterministic replay given a fixed seed
- Checkpoint and resume mid-episode

**Non-Goals:**
- LLM agent integration (Phase 1)
- Evolutionary optimization / fitness landscapes (Phase 1+)
- Web dashboard or real-time visualization (separate change)
- Multi-episode batch execution or parameter sweeps (separate change)
- TOML config support (defer; JSON first, TOML is nice-to-have)

## Decisions

### D1: SimulationConfig wraps WorldConfig, not replaces it

`SimulationConfig` holds simulation-level parameters (seed, ticks_per_episode, checkpoint_interval, agent_mix, debug flags) and constructs a `WorldConfig` for world generation. This avoids duplicating all WorldConfig fields and keeps the engine's config boundary clean.

**Alternative**: Merge everything into one config class. Rejected because WorldConfig is already frozen into WorldState and changing it would touch every engine module.

### D2: Runner uses AgentDecisionsFn callback pattern

The runner constructs the `AgentDecisionsFn` closure that dispatches observations to the appropriate `BaseAgent.decide()` for each agent. This keeps the runner compatible with `execute_tick`'s existing interface without modifying the engine.

**Alternative**: Modify `execute_tick` to accept a dict of agents. Rejected because it would change the engine's stable API.

### D3: Agent registry maps agent_id to BaseAgent instance

The runner maintains a `dict[str, BaseAgent]` mapping. When agents die and respawn (new IDs), the runner calls `AgentFactory.create_agent()` to get a new BaseAgent and inserts it. This decouples agent lifecycle from the engine's spawn logic.

### D4: Heuristic agents use simple state machines

Each heuristic agent type implements a small finite state machine (e.g., Harvester: MOVE_TO_RESOURCE → HARVEST → MOVE_TO_HUB → SELL → repeat). State is stored on the agent instance. No complex planning. This keeps agents fast and predictable.

**Alternative**: Rule-based scoring (evaluate all actions, pick highest score). Considered but more complex to debug and tune for Phase 0.

### D5: EventLogger uses WAL mode SQLite with batched inserts

One SQLite database per episode. WAL mode for concurrent read during writes. All events for a tick are batched into a single transaction. Schema uses 6 tables: ticks, actions, trades, deaths, messages, agent_snapshots.

**Alternative**: Append-only JSON log files. Rejected because SQL queries are essential for post-hoc analysis.

### D6: Checkpointing uses WorldState.to_json()

Checkpoints serialize the full WorldState via its existing `to_json()` method, plus the RNG state and agent registry metadata. Resume deserializes via `WorldState.from_json()` and reconstructs the agent registry.

### D7: Metrics computation at two levels

- **TickMetrics** (already exists in engine): per-tick aggregates computed by `execute_tick`
- **EpisodeMetrics**: computed at episode end from the full tick history and final world state. Includes Gini coefficient, mean/max lifetime, trade totals, etc.

No new per-tick metric computation in the runner — it reuses what `execute_tick` already produces.

### D8: CLI uses argparse, not click/typer

Minimal dependency footprint for Phase 0. Three subcommands: `run`, `analyze`, `resume`. The `run` subcommand accepts `--config`, `--seed`, `--fast` flags.

## Risks / Trade-offs

- **[Risk] Heuristic agents might all converge to same strategy** → Mitigation: 5 distinct archetypes with different priorities; configurable aggression/pricing parameters
- **[Risk] Economy might not reach equilibrium in 500 ticks** → Mitigation: tune starting_credits, survival_tax, and npc_budget_replenish_rate; runner reports per-tick metrics for diagnosis
- **[Risk] SQLite logging might slow hyperfast mode** → Mitigation: batched writes per tick, WAL mode; `--fast` flag disables logging entirely
- **[Risk] Agent state machines may produce degenerate behavior** → Mitigation: each agent adds small randomness to tie-breaking decisions using a per-agent RNG seeded from the world RNG
- **[Trade-off] SimulationConfig uses user-facing credits (floats) vs engine millicredits (ints)** → Config validates and converts at construction time; all internal values remain millicredits
