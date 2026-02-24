## ADDED Requirements

### Requirement: BaseAgent abstract class
The system SHALL provide a `BaseAgent` abstract base class with two abstract methods: `decide(observation: AgentObservation) -> AgentTurnResult` and `on_spawn(agent_id: str, config: SimulationConfig) -> None`.

#### Scenario: Subclass must implement decide
- **WHEN** a class inherits from `BaseAgent` without implementing `decide`
- **THEN** instantiation raises `TypeError`

#### Scenario: Subclass must implement on_spawn
- **WHEN** a class inherits from `BaseAgent` without implementing `on_spawn`
- **THEN** instantiation raises `TypeError`

### Requirement: AgentFactory protocol
The system SHALL provide an `AgentFactory` abstract base class with an abstract method `create_agent(agent_id: str) -> BaseAgent`.

#### Scenario: Factory creates agents
- **WHEN** `factory.create_agent("agent_005")` is called
- **THEN** a `BaseAgent` instance is returned with the agent configured for the given ID

### Requirement: Agent decides from observation
`BaseAgent.decide()` SHALL accept an `AgentObservation` and return an `AgentTurnResult` containing an `Action` and an optional scratchpad update.

#### Scenario: Agent returns valid action
- **WHEN** `agent.decide(observation)` is called
- **THEN** the returned `AgentTurnResult` contains a valid `Action` (one of the defined action types)

### Requirement: Agent initialization on spawn
`BaseAgent.on_spawn()` SHALL be called exactly once when the agent is first created, before any `decide()` calls.

#### Scenario: on_spawn called before decide
- **WHEN** a new agent is spawned
- **THEN** `on_spawn(agent_id, config)` is called, then `decide()` is callable
