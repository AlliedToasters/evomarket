## ADDED Requirements

### Requirement: Episode execution
The `SimulationRunner` SHALL execute a complete episode by: generating a world from config + seed, spawning the initial agent population, running ticks up to `ticks_per_episode`, collecting metrics, and returning an `EpisodeResult`.

#### Scenario: Full episode completes
- **WHEN** `run_episode(config, agent_factory)` is called with a valid config and factory
- **THEN** the simulation runs for `ticks_per_episode` ticks and returns an `EpisodeResult` containing final world state, tick metrics, agent summaries, and episode metrics

#### Scenario: Early termination on total population death
- **WHEN** all agents die before `ticks_per_episode`
- **THEN** the episode terminates early and the `EpisodeResult` records the actual tick count

### Requirement: Graceful KeyboardInterrupt handling
When a `KeyboardInterrupt` (Ctrl+C) is received during the tick loop, the runner SHALL catch the exception, log a message, and proceed to flush the event logger, compute metrics, and return a valid `EpisodeResult` with partial data.

#### Scenario: Ctrl+C during episode
- **WHEN** the user presses Ctrl+C at tick 50 of a 200-tick episode
- **THEN** the episode stops after tick 50, event logs are flushed, and an `EpisodeResult` with 50 ticks of data is returned

### Requirement: Pluggable stop condition
`run_episode` SHALL accept an optional `stop_condition: Callable[[int, WorldState, TickResult], bool]` callback. When provided, it is called after each tick's events are logged. If it returns `True`, the episode terminates early.

#### Scenario: Custom stop condition triggers
- **WHEN** `stop_condition` returns True at tick 30
- **THEN** the episode stops after tick 30 and returns a valid `EpisodeResult`

#### Scenario: Stop condition not provided
- **WHEN** `stop_condition` is None
- **THEN** the episode runs until `ticks_per_episode` or all agents die

### Requirement: Idle streak stop condition
The module SHALL export `idle_streak_stop(max_idle_ticks) -> StopCondition` which returns a stop condition that triggers after N consecutive ticks with no productive actions. Productive actions are: `harvest`, `accept_order`, `accept_trade`, `propose_trade`, and any NPC sale.

#### Scenario: Idle streak triggers early stop
- **WHEN** 15 consecutive ticks have only `post_order`, `idle`, or `move` actions and `max_idle_ticks=10`
- **THEN** the stop condition returns True at the 10th idle tick

#### Scenario: Productive action resets streak
- **WHEN** an agent harvests on tick 8 of a 10-tick idle streak
- **THEN** the streak resets to 0 and the episode continues

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
The runner SHALL save a full world state checkpoint every `checkpoint_interval` ticks (configurable). Checkpoints SHALL include the serialized `WorldState`, agent controller state (via `BaseAgent.get_state()`), and enough metadata to resume.

#### Scenario: Checkpoint at interval
- **WHEN** tick 50 completes and `checkpoint_interval=50`
- **THEN** a checkpoint file is written containing the serialized world state and agent controller states

#### Scenario: No checkpoint when interval is 0
- **WHEN** `checkpoint_interval=0`
- **THEN** no checkpoints are written during the episode

#### Scenario: Auto-checkpoint on KeyboardInterrupt
- **WHEN** the user presses Ctrl+C during a running episode with output_dir set
- **THEN** a checkpoint is saved before the episode returns partial results

#### Scenario: Auto-checkpoint on early stop
- **WHEN** a stop_condition triggers early termination with output_dir set
- **THEN** a checkpoint is saved before the episode returns partial results

### Requirement: Agent state serialization
Agent controllers SHALL support optional state serialization via `BaseAgent.get_state() -> dict | None` and `BaseAgent.set_state(state: dict)`. The runner SHALL call `get_state()` on each agent when saving checkpoints and `set_state()` when restoring from checkpoints. This preserves agent-internal state (scratchpads, state machines, price memory, RNG state) across save/resume cycles.

#### Scenario: Heuristic agent state round-trips
- **WHEN** a HarvesterAgent in "selling" state with 5 ticks elapsed is checkpointed and restored
- **THEN** the restored agent resumes in "selling" state with `_ticks_in_state=5` and identical RNG state

#### Scenario: LLM agent scratchpad preserved
- **WHEN** an LLMAgent with scratchpad content is checkpointed and restored
- **THEN** the restored agent has the same scratchpad content

#### Scenario: Agent with no state returns None
- **WHEN** `get_state()` is called on an agent that doesn't override it
- **THEN** it returns None and no state is saved for that agent

### Requirement: Resume from checkpoint
The runner SHALL support resuming an episode from a checkpoint file, restoring world state and agent controller state, then continuing execution from the checkpointed tick.

#### Scenario: Resume continues from checkpoint
- **WHEN** a checkpoint from tick 100 is loaded and `run_episode` is called with `resume=True`
- **THEN** execution continues from tick 101 through `ticks_per_episode`

#### Scenario: Resume restores agent controller state
- **WHEN** a checkpoint containing agent_state is loaded
- **THEN** each agent's `set_state()` is called with its saved state, restoring internal state machines, scratchpads, and RNG positions

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
