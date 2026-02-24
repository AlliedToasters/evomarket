## ADDED Requirements

### Requirement: Tick phase ordering
The tick engine SHALL execute exactly 10 phases in strict order: RECEIVE, OBSERVE, DECIDE, VALIDATE, RESOLVE, TAX, DEATH, SPAWN, REPLENISH, LOG. No phase SHALL be skipped or reordered.

#### Scenario: All phases execute in order
- **WHEN** `execute_tick` is called with a valid world state and agent_decisions callable
- **THEN** phases execute in the order RECEIVE → OBSERVE → DECIDE → VALIDATE → RESOLVE → TAX → DEATH → SPAWN → REPLENISH → LOG

#### Scenario: Phase effects are visible to subsequent phases
- **WHEN** RECEIVE delivers messages
- **THEN** OBSERVE includes those messages in agent observations

### Requirement: execute_tick function signature
The tick engine SHALL expose `execute_tick(world: WorldState, agent_decisions: Callable[[dict[str, AgentObservation]], dict[str, AgentTurnResult]], debug: bool = False) -> TickResult` as its primary entry point. The function SHALL mutate `world` in place and return a `TickResult` capturing all outcomes.

#### Scenario: Basic tick execution
- **WHEN** `execute_tick` is called with a world containing living agents and a callable that returns valid actions
- **THEN** it returns a `TickResult` with all phase results populated and the world state is updated

#### Scenario: Tick increments world tick counter
- **WHEN** `execute_tick` completes
- **THEN** `world.tick` is incremented by 1

### Requirement: RECEIVE phase delivers pending messages
The RECEIVE phase SHALL call `deliver_pending_messages(world)` to deliver all messages queued in the previous tick.

#### Scenario: Messages from previous tick are delivered
- **WHEN** pending messages exist from the previous tick
- **THEN** RECEIVE delivers them to recipients' inboxes before OBSERVE runs

### Requirement: DECIDE phase applies scratchpad updates
The DECIDE phase SHALL apply `scratchpad_update` from each `AgentTurnResult` to the corresponding agent's `prompt_document` field, if the update is not None.

#### Scenario: Scratchpad update applied
- **WHEN** an agent's `AgentTurnResult` has `scratchpad_update = "new notes"`
- **THEN** the agent's `prompt_document` is set to `"new notes"` before VALIDATE runs

#### Scenario: Null scratchpad update preserves existing document
- **WHEN** an agent's `AgentTurnResult` has `scratchpad_update = None`
- **THEN** the agent's `prompt_document` is unchanged

### Requirement: VALIDATE phase converts invalid actions to idle
The VALIDATE phase SHALL call `validate_action(agent_id, action, world)` for each agent's action. Invalid actions SHALL be replaced with `IdleAction`.

#### Scenario: Invalid action becomes idle
- **WHEN** an agent submits a MoveAction to a non-adjacent node
- **THEN** VALIDATE replaces it with IdleAction and logs a warning

### Requirement: RESOLVE phase executes validated actions
The RESOLVE phase SHALL call `resolve_actions(world, validated_actions)` to execute all validated actions with deterministic priority ordering. Before resolving, it SHALL expire pending trade proposals from previous ticks.

#### Scenario: Actions resolved with priority ordering
- **WHEN** two agents attempt to accept the same order
- **THEN** the agent with higher random priority succeeds; the other fails

#### Scenario: Trade proposals from previous tick expire before resolution
- **WHEN** trade proposals exist from a previous tick
- **THEN** they are expired before current-tick actions are resolved

### Requirement: TAX phase collects survival tax
The TAX phase SHALL collect `config.survival_tax` from each living agent not in grace period. Agents with `grace_ticks_remaining > 0` SHALL have their grace decremented and skip tax. The phase SHALL return a list of `TaxResult` and identify agents with balance ≤ 0.

#### Scenario: Agent pays full tax
- **WHEN** a living agent has credits > survival_tax and grace_ticks_remaining == 0
- **THEN** survival_tax is transferred from agent to treasury

#### Scenario: Agent in grace period skips tax
- **WHEN** a living agent has grace_ticks_remaining == 3
- **THEN** grace is decremented to 2 and no tax is collected

#### Scenario: Agent with insufficient credits is marked for death
- **WHEN** an agent has 500 millicredits and survival_tax is 1000
- **THEN** 500 is collected, balance becomes 0, and agent is identified for death

### Requirement: DEATH phase resolves agent deaths
The DEATH phase SHALL call `resolve_deaths(world, dead_agent_ids)` with cleanup callbacks for orders and messages. Dead agents' orders SHALL be cancelled and their messages cleared.

#### Scenario: Dead agent's orders are cancelled
- **WHEN** an agent dies with active orders
- **THEN** all their orders are cancelled during death resolution

#### Scenario: Dead agent's messages are cleared
- **WHEN** an agent dies with pending messages
- **THEN** their pending messages (sent and received) are removed

### Requirement: SPAWN phase replaces dead agents
The SPAWN phase SHALL spawn replacement agents when population drops below `config.population_size`, funding each with `config.starting_credits` from treasury via `fund_spawn()`. Spawning SHALL stop if treasury cannot fund a spawn.

#### Scenario: Agent spawned to replace dead agent
- **WHEN** population is 19 and target is 20 and treasury has sufficient funds
- **THEN** 1 new agent is spawned with starting_credits and grace_ticks_remaining

#### Scenario: Spawn blocked by insufficient treasury
- **WHEN** treasury has fewer credits than starting_credits
- **THEN** no agent is spawned

### Requirement: REPLENISH phase restores resources and budgets
The REPLENISH phase SHALL execute three sub-operations in order: (1) replenish NPC budgets from treasury, (2) regenerate node resources, (3) decay NPC stockpiles.

#### Scenario: All three sub-operations execute
- **WHEN** REPLENISH runs
- **THEN** NPC budgets increase, resource stockpiles grow, and NPC stockpiles decay

### Requirement: LOG phase increments agent ages
The LOG phase SHALL increment the `age` field of all living agents by 1.

#### Scenario: Living agents age
- **WHEN** LOG phase runs
- **THEN** each living agent's age increases by 1

#### Scenario: Dead agents do not age
- **WHEN** LOG phase runs and an agent died this tick
- **THEN** the dead agent's age is not incremented

### Requirement: Invariant checking
In debug mode (`debug=True`), the tick engine SHALL call `world.verify_invariant()` after every phase. In normal mode, it SHALL verify only at the end of the tick. The invariant check result SHALL be recorded in `TickResult.invariant_check`.

#### Scenario: Debug mode checks after every phase
- **WHEN** `execute_tick` is called with `debug=True`
- **THEN** `verify_invariant()` is called after each of the 10 phases

#### Scenario: Normal mode checks only at end
- **WHEN** `execute_tick` is called with `debug=False`
- **THEN** `verify_invariant()` is called only once, after LOG phase

### Requirement: Deterministic execution
Given the same world state (including RNG state) and the same agent_decisions callable returning the same results, `execute_tick` SHALL produce identical `TickResult` and identical post-tick world state.

#### Scenario: Reproducible tick results
- **WHEN** `execute_tick` is called twice with identical world snapshots and identical agent decisions
- **THEN** both calls produce identical TickResult values

### Requirement: TickResult captures all outcomes
`TickResult` SHALL contain: `tick` (int), `action_results` (list[ActionResult]), `tax_results` (list[TaxResult]), `death_results` (list[DeathResult]), `spawn_results` (list[SpawnResult]), `replenish_result` (ReplenishResult), `metrics` (TickMetrics), `invariant_check` (bool).

#### Scenario: TickResult populated after normal tick
- **WHEN** a tick completes with 2 deaths and 1 spawn
- **THEN** TickResult has 2 entries in death_results, 1 in spawn_results, and all other fields populated

### Requirement: TickMetrics aggregates tick statistics
`TickMetrics` SHALL contain: `total_credits_in_circulation` (Millicredits), `agent_credit_gini` (float), `total_trade_volume` (Millicredits), `trades_executed` (int), `agents_alive` (int), `agents_died` (int), `agents_spawned` (int), `total_resources_harvested` (int), `total_npc_sales` (int), `total_messages_sent` (int).

#### Scenario: Metrics computed from tick results
- **WHEN** a tick completes with 3 successful harvests, 1 trade, and 5 messages
- **THEN** TickMetrics shows total_resources_harvested=3, trades_executed=1, total_messages_sent=5
