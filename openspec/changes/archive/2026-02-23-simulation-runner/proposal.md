## Why

The game engine components (tick pipeline, actions, trading, inheritance, communication) are implemented but have no top-level orchestrator. Without a simulation runner and agents to drive decisions, the engine cannot execute episodes, validate economic dynamics, or prove the game works. This is the capstone integration for Phase 0.

## What Changes

- Add `SimulationConfig` dataclass consolidating all game parameters (world, economy, population, trading, death, simulation control, debug flags), serializable to/from JSON and TOML
- Add `SimulationRunner` that executes full episodes: world generation, initial population spawn, tick loop with agent decisions, metric collection, checkpointing, and termination
- Add `EpisodeResult`, `AgentSummary`, and `EpisodeMetrics` models capturing episode outcomes
- Add abstract `BaseAgent` interface (`decide`, `on_spawn`) and `AgentFactory` protocol for pluggable agent implementations
- Add `RandomAgent` (uniformly random valid actions) for baseline invariant testing
- Add 5 heuristic agent strategies (`Harvester`, `Trader`, `Social`, `Hoarder`, `Explorer`) creating a diverse economy for Phase 0 validation
- Add `EventLogger` writing structured events to SQLite (ticks, actions, trades, deaths, messages, agent snapshots) with batched per-tick writes
- Add CLI entry point (`python -m evomarket run/analyze/resume`) for running simulations from the command line

## Capabilities

### New Capabilities
- `simulation-config`: Unified configuration object for all simulation parameters, with JSON/TOML serialization and validation
- `simulation-runner`: Episode execution orchestrator — main loop, checkpointing, termination, result aggregation
- `agent-interface`: Abstract agent interface and factory protocol for pluggable decision-makers
- `heuristic-agents`: Five heuristic agent strategies (Harvester, Trader, Social, Hoarder, Explorer) plus a random baseline agent
- `event-logging`: SQLite-backed structured event logging with batched writes and queryable tables
- `simulation-cli`: Command-line interface for running, analyzing, and resuming simulations

### Modified Capabilities
_(none — all existing engine specs remain unchanged; the runner consumes their public interfaces)_

## Impact

- **New files**: `evomarket/simulation/{runner,config,metrics,logging}.py`, `evomarket/agents/{base,random_agent,heuristic_agent}.py`, `evomarket/cli.py`, `tests/{test_runner,test_heuristic_agents}.py`
- **Dependencies**: Uses `execute_tick` from `engine/tick.py`, `generate_world`/`WorldState`/`WorldConfig` from `core/world.py`, `AgentObservation`/`AgentTurnResult` from engine modules. No new external packages (sqlite3 is stdlib).
- **Entry point**: Adds `evomarket/__main__.py` for `python -m evomarket` invocation
