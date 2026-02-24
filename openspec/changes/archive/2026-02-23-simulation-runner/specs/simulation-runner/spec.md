## ADDED Requirements

### Requirement: Episode execution
The `SimulationRunner` SHALL execute a complete episode by: generating a world from config + seed, spawning the initial agent population, running ticks up to `ticks_per_episode`, collecting metrics, and returning an `EpisodeResult`.

#### Scenario: Full episode completes
- **WHEN** `run_episode(config, agent_factory)` is called with a valid config and factory
- **THEN** the simulation runs for `ticks_per_episode` ticks and returns an `EpisodeResult` containing final world state, tick metrics, agent summaries, and episode metrics

#### Scenario: Early termination on total population death
- **WHEN** all agents die before `ticks_per_episode`
- **THEN** the episode terminates early and the `EpisodeResult` records the actual tick count

### Requirement: Agent decision dispatch
The runner SHALL construct an `AgentDecisionsFn` closure that dispatches `AgentObservation` objects to the corresponding `BaseAgent.decide()` method for each living agent, and collects `AgentTurnResult` responses.

#### Scenario: Each agent receives its observation
- **WHEN** a tick executes with 3 living agents
- **THEN** each agent's `decide()` method is called exactly once with its own `AgentObservation`

#### Scenario: Dead agents are not queried
- **WHEN** an agent dies during a tick
- **THEN** its `decide()` method is NOT called on subsequent ticks

### Requirement: Agent lifecycle management
The runner SHALL maintain a registry mapping `agent_id` to `BaseAgent` instances. When the engine spawns a new agent, the runner SHALL call `AgentFactory.create_agent()` and register the new instance.

#### Scenario: Spawned agent gets registered
- **WHEN** the engine spawns agent `agent_025` during a tick
- **THEN** the runner calls `agent_factory.create_agent("agent_025")` and adds it to the registry

#### Scenario: Dead agent stays in registry
- **WHEN** agent `agent_003` dies
- **THEN** the registry entry remains (for summary generation) but `decide()` is no longer called

### Requirement: Checkpointing
The runner SHALL save a full world state checkpoint every `checkpoint_interval` ticks (configurable). Checkpoints SHALL include the serialized `WorldState` and enough metadata to resume.

#### Scenario: Checkpoint at interval
- **WHEN** tick 50 completes and `checkpoint_interval=50`
- **THEN** a checkpoint file is written containing the serialized world state

#### Scenario: No checkpoint when interval is 0
- **WHEN** `checkpoint_interval=0`
- **THEN** no checkpoints are written during the episode

### Requirement: Resume from checkpoint
The runner SHALL support resuming an episode from a checkpoint file, restoring world state and continuing execution from the checkpointed tick.

#### Scenario: Resume continues from checkpoint
- **WHEN** a checkpoint from tick 100 is loaded and `run_episode` is called with `resume=True`
- **THEN** execution continues from tick 101 through `ticks_per_episode`

### Requirement: Deterministic execution
Given a fixed seed, the runner SHALL produce identical `EpisodeResult` across runs. All randomness (including agent tie-breaking) SHALL flow through seeded RNGs.

#### Scenario: Same seed produces same result
- **WHEN** two episodes run with identical `SimulationConfig` (same seed)
- **THEN** the `EpisodeResult` objects are identical (same tick metrics, same agent summaries)

### Requirement: EpisodeResult model
The runner SHALL return an `EpisodeResult` containing: config, final world state, list of `TickMetrics`, list of `AgentSummary`, and `EpisodeMetrics`.

#### Scenario: EpisodeResult contains all fields
- **WHEN** an episode completes
- **THEN** the result contains non-null config, final_world_state, tick_metrics (length = ticks executed), agent_summaries (one per agent that ever existed), and episode_metrics

### Requirement: AgentSummary model
`AgentSummary` SHALL capture per-agent outcomes: agent_id, final_credits, final_inventory, final_net_worth (credits + liquidation value), lifetime, total_trades, total_messages, cause_of_death, and prompt_document_at_death.

#### Scenario: Summary for surviving agent
- **WHEN** an agent survives the full episode
- **THEN** its summary has `cause_of_death=None` and `lifetime=ticks_per_episode`

#### Scenario: Summary for dead agent
- **WHEN** an agent dies at tick 42 from tax insolvency
- **THEN** its summary has `cause_of_death="tax_insolvency"`, `lifetime=42`, and `prompt_document_at_death` set

### Requirement: EpisodeMetrics model
`EpisodeMetrics` SHALL compute aggregate statistics: mean_lifetime, max_lifetime, mean_net_worth, max_net_worth, total_trades, total_deaths, final_gini, final_treasury.

#### Scenario: Metrics computed from tick history
- **WHEN** an episode with 20 agents completes
- **THEN** `EpisodeMetrics` contains valid aggregate values computed from all tick results and agent summaries
