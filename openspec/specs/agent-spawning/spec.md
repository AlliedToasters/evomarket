## ADDED Requirements

### Requirement: Spawn replaces dead agents up to population target
`spawn_agents(world: WorldState) -> list[SpawnResult]` SHALL create new agents when the living population is below `config.population_size`. It SHALL spawn up to `population_size - current_alive` agents per tick.

#### Scenario: One agent spawned to fill gap
- **WHEN** 19 agents are alive and population_size is 20 and treasury has sufficient funds
- **THEN** 1 agent is spawned

#### Scenario: Multiple agents spawned after mass death
- **WHEN** 15 agents are alive and population_size is 20 and treasury has sufficient funds
- **THEN** 5 agents are spawned

#### Scenario: No spawn when population is at target
- **WHEN** 20 agents are alive and population_size is 20
- **THEN** no agents are spawned

### Requirement: Spawn funded from treasury
Each spawn SHALL be funded by calling `fund_spawn(world, config.starting_credits)`. If the treasury cannot fund a spawn, spawning SHALL stop for this tick.

#### Scenario: Treasury funds spawn
- **WHEN** treasury has 100000mc and starting_credits is 30000mc
- **THEN** spawn succeeds and treasury decreases by 30000mc

#### Scenario: Treasury exhausted mid-spawn
- **WHEN** 3 agents need spawning but treasury can only fund 2
- **THEN** 2 agents spawn and 1 is deferred to a future tick

### Requirement: Spawned agent initialization
Each spawned agent SHALL have: a unique agent_id (format `agent_{NNN}`), a display name, location at a random SPAWN-type node, credits equal to `config.starting_credits`, empty inventory (all commodity quantities = 0), age 0, alive = True, empty will, empty prompt_document, and `grace_ticks_remaining` equal to `config.spawn_grace_period`.

#### Scenario: Agent initialized correctly
- **WHEN** a new agent is spawned
- **THEN** it has the correct starting credits, zero inventory, full grace period, and is located at a SPAWN node

### Requirement: Deterministic agent ID assignment
Agent IDs SHALL be assigned using `world.next_agent_id`, incrementing after each spawn. The format SHALL be `agent_{next_agent_id:03d}`.

#### Scenario: Sequential IDs assigned
- **WHEN** world.next_agent_id is 20 and 2 agents spawn
- **THEN** they get IDs "agent_020" and "agent_021", and next_agent_id becomes 22

### Requirement: Spawn location selection
Spawned agents SHALL be placed at a SPAWN-type node selected using `world.rng`. If no SPAWN nodes exist, any node SHALL be used.

#### Scenario: Agent spawns at spawn node
- **WHEN** the world has 1 SPAWN-type node "node_spawn"
- **THEN** the spawned agent's location is "node_spawn"

### Requirement: SpawnResult captures spawn details
Each spawn SHALL produce a `SpawnResult` containing agent_id, location, and starting_credits.

#### Scenario: SpawnResult populated
- **WHEN** agent "agent_020" spawns at "node_spawn" with 30000mc
- **THEN** SpawnResult has agent_id="agent_020", location="node_spawn", starting_credits=30000
