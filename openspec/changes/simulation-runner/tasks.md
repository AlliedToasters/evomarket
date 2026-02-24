## 1. SimulationConfig

- [x] 1.1 Create `evomarket/simulation/config.py` with `SimulationConfig` dataclass: all parameters from proposal with sensible defaults, `agent_mix` field, validation, and `to_world_config()` method with credit→millicredit conversion
- [x] 1.2 Add JSON serialization/deserialization (`to_json`, `from_json`) to `SimulationConfig`
- [x] 1.3 Write tests in `tests/test_config.py`: default construction, credit conversion, round-trip serialization, validation errors for bad params

## 2. Agent Interface

- [x] 2.1 Create `evomarket/agents/base.py` with `BaseAgent` ABC (`decide`, `on_spawn`) and `AgentFactory` ABC (`create_agent`)
- [x] 2.2 Write tests in `tests/test_agents_base.py`: verify ABC enforcement (missing methods raise TypeError), basic subclass works

## 3. Random Agent

- [x] 3.1 Create `evomarket/agents/random_agent.py` with `RandomAgent` implementation: filters valid actions from observation, selects uniformly at random, uses per-agent seeded RNG
- [x] 3.2 Create `RandomAgentFactory` that creates `RandomAgent` instances with deterministic seeds derived from agent_id
- [x] 3.3 Write tests: valid action selection across different observation states, determinism with same seed

## 4. Heuristic Agents

- [x] 4.1 Create `evomarket/agents/heuristic_agent.py` with `HarvesterAgent`: state machine (MOVE_TO_RESOURCE → HARVEST → MOVE_TO_HUB → SELL → repeat), pathfinding to nearest target node type
- [x] 4.2 Add `TraderAgent`: tracks observed prices, buys at low-price nodes, moves to high-price nodes, sells
- [x] 4.3 Add `SocialAgent`: stays at populated nodes, posts orders, sends trade proposals to co-located agents, accepts favorable incoming trades
- [x] 4.4 Add `HoarderAgent`: harvests and holds, only sells when credits near survival tax threshold, updates will with nearby agents
- [x] 4.5 Add `ExplorerAgent`: moves every 1-2 ticks, inspects agents, broadcasts messages about conditions
- [x] 4.6 Create `HeuristicAgentFactory` that creates agents based on `agent_mix` config, distributing types round-robin
- [x] 4.7 Write tests in `tests/test_heuristic_agents.py`: each agent type produces valid actions, state machine transitions work, factory distributes types correctly

## 5. Event Logging

- [x] 5.1 Create `evomarket/simulation/logging.py` with `EventLogger`: SQLite database creation (6 tables), WAL mode, batched writes per tick
- [x] 5.2 Implement `log_tick`, `log_actions`, `log_trades`, `log_deaths`, `log_messages`, `log_agent_snapshots`, and `flush_tick` methods
- [x] 5.3 Implement no-op mode (`enabled=False`) that silently ignores all log calls
- [x] 5.4 Write tests in `tests/test_event_logging.py`: database creation, correct schema, batched inserts, no-op mode, WAL mode check

## 6. Simulation Runner

- [x] 6.1 Create `evomarket/simulation/runner.py` with `run_episode(config, agent_factory)`: world generation, initial agent registration, tick loop with decision dispatch
- [x] 6.2 Implement agent lifecycle management: register new agents on spawn, track dead agents, generate AgentSummary for each agent
- [x] 6.3 Implement checkpointing: save WorldState.to_json() at checkpoint_interval, with agent registry metadata
- [x] 6.4 Implement resume from checkpoint: load WorldState.from_json(), reconstruct agent registry, continue from checkpointed tick
- [x] 6.5 Implement EpisodeResult, AgentSummary, and EpisodeMetrics models with computation from tick history
- [x] 6.6 Integrate EventLogger into the tick loop (log tick results, actions, trades, deaths, messages, snapshots)
- [x] 6.7 Write tests in `tests/test_runner.py`: full episode completion, early termination, determinism (same seed = same result), checkpoint/resume round-trip

## 7. CLI

- [x] 7.1 Create `evomarket/cli.py` with argparse-based CLI: `run`, `analyze`, `resume` subcommands
- [x] 7.2 Create `evomarket/__main__.py` entry point that invokes the CLI
- [x] 7.3 Implement `run` subcommand: load config, override seed, output directory creation, episode execution, result saving
- [x] 7.4 Implement `analyze` subcommand: open SQLite database, query and print summary statistics
- [x] 7.5 Implement `resume` subcommand: load checkpoint, continue episode
- [x] 7.6 Write tests in `tests/test_cli.py`: argument parsing, output directory structure, fast mode behavior

## 8. Integration Validation

- [x] 8.1 Run full 500-tick episode with 20 heuristic agents: no crashes, no invariant violations
- [x] 8.2 Verify acceptance criteria: some agents survive, some die; trade volume > 0; NPC prices fluctuate; Gini changes over time; treasury above minimum reserve
- [x] 8.3 Verify hyperfast mode: >=1000 ticks/second with logging disabled
- [x] 8.4 Verify determinism: two runs with same seed produce identical results
