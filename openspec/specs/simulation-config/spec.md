## ADDED Requirements

### Requirement: SimulationConfig dataclass
The system SHALL provide a `SimulationConfig` dataclass that holds all simulation-level parameters: seed, ticks_per_episode, checkpoint_interval, agent_mix, mode, debug flags, and all economic parameters needed to construct a `WorldConfig`.

#### Scenario: Default config is valid
- **WHEN** a `SimulationConfig` is constructed with no arguments
- **THEN** all fields have sensible defaults and validation passes

#### Scenario: Config constructs WorldConfig
- **WHEN** `SimulationConfig.to_world_config()` is called
- **THEN** a valid `WorldConfig` is returned with all economic parameters converted from user-facing credits (floats) to millicredits (ints)

### Requirement: Credit unit conversion
`SimulationConfig` SHALL accept user-facing credit values as floats (e.g., `survival_tax=1.0` means 1 credit) and convert them to millicredits (integers, 1 credit = 1000 millicredits) when constructing a `WorldConfig`.

#### Scenario: Float credits convert to millicredits
- **WHEN** `SimulationConfig(survival_tax=1.0).to_world_config()` is called
- **THEN** the resulting `WorldConfig.survival_tax` equals `1000`

#### Scenario: Fractional credits convert correctly
- **WHEN** `SimulationConfig(starting_credits=30.5).to_world_config()` is called
- **THEN** the resulting `WorldConfig.starting_credits` equals `30500`

### Requirement: JSON serialization
`SimulationConfig` SHALL be serializable to and deserializable from JSON, producing identical configs on round-trip.

#### Scenario: Round-trip serialization
- **WHEN** a `SimulationConfig` is serialized to JSON and deserialized back
- **THEN** the resulting config equals the original

### Requirement: Agent mix configuration
`SimulationConfig` SHALL include an `agent_mix` field specifying the distribution of agent types. The default mix SHALL include all heuristic agent types.

#### Scenario: Default agent mix
- **WHEN** `SimulationConfig` is constructed with no `agent_mix`
- **THEN** the default mix includes harvester, trader, social, hoarder, and explorer types

#### Scenario: Custom agent mix
- **WHEN** `SimulationConfig(agent_mix={"harvester": 10, "trader": 10})` is constructed
- **THEN** the agent mix contains only harvester and trader types with the specified counts

### Requirement: Config validation
`SimulationConfig` SHALL validate that parameter combinations are consistent (e.g., total population matches agent_mix sum, total_credit_supply can fund the starting population).

#### Scenario: Population mismatch rejected
- **WHEN** `SimulationConfig(population_size=20, agent_mix={"harvester": 5})` is constructed
- **THEN** validation raises an error because agent_mix sum (5) does not match population_size (20)

#### Scenario: Insufficient credit supply rejected
- **WHEN** `SimulationConfig(total_credit_supply=10, starting_credits=30, population_size=20)` is constructed
- **THEN** validation raises an error because supply cannot fund starting credits
