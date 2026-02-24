## ADDED Requirements

### Requirement: LLMAgent implements BaseAgent
The system SHALL provide an `LLMAgent` class in `evomarket/agents/llm_agent.py` that extends `BaseAgent` and implements `decide()` and `on_spawn()`.

#### Scenario: LLMAgent is a valid BaseAgent
- **WHEN** `LLMAgent` is instantiated with a valid `LLMBackend`
- **THEN** it satisfies the `BaseAgent` interface and can be used anywhere a `BaseAgent` is expected

### Requirement: LLMAgent.decide orchestrates prompt-call-parse pipeline
`LLMAgent.decide(observation)` SHALL render the observation to a text prompt, call the LLM backend, parse the response into an `Action`, and return an `AgentTurnResult`.

#### Scenario: Successful decide cycle
- **WHEN** `decide(observation)` is called with a valid `AgentObservation`
- **THEN** the prompt renderer is called with the observation and current scratchpad
- **AND** the LLM backend is called with the rendered prompt
- **AND** the action parser extracts an `Action` and optional scratchpad update from the LLM response
- **AND** an `AgentTurnResult` is returned with the parsed action and scratchpad update

#### Scenario: LLM backend failure returns idle
- **WHEN** `decide(observation)` is called and the LLM backend raises an exception or returns empty
- **THEN** an `AgentTurnResult` with `IdleAction` is returned
- **AND** the failure is logged

### Requirement: LLMAgent maintains persistent scratchpad
`LLMAgent` SHALL maintain a scratchpad string that persists across `decide()` calls. When the action parser extracts a scratchpad update from the LLM response, the agent SHALL update its internal scratchpad and include the update in the `AgentTurnResult.scratchpad_update` field.

#### Scenario: Scratchpad persists across ticks
- **WHEN** the LLM response includes a SCRATCHPAD section on tick N
- **THEN** the scratchpad content is included in the prompt on tick N+1

#### Scenario: Scratchpad update propagated to engine
- **WHEN** the action parser extracts a scratchpad update
- **THEN** `AgentTurnResult.scratchpad_update` contains the new scratchpad text
- **AND** the engine stores it in `agent.prompt_document`

### Requirement: LLMAgent.on_spawn stores agent ID and config
`LLMAgent.on_spawn(agent_id, config)` SHALL store the agent ID for use in prompt rendering.

#### Scenario: on_spawn initializes agent
- **WHEN** `on_spawn("agent_005", config)` is called
- **THEN** subsequent `decide()` calls include "agent_005" in the rendered prompt

### Requirement: LLMAgentFactory creates LLMAgent instances
The system SHALL provide an `LLMAgentFactory` class implementing `AgentFactory` that creates `LLMAgent` instances sharing a single `LLMBackend`.

#### Scenario: Factory creates agents with shared backend
- **WHEN** `factory.create_agent("agent_001")` and `factory.create_agent("agent_002")` are called
- **THEN** both returned `LLMAgent` instances use the same `LLMBackend` instance

#### Scenario: Factory calls on_spawn
- **WHEN** `factory.create_agent("agent_003")` is called
- **THEN** `on_spawn("agent_003", config)` is called on the returned agent before it is returned
