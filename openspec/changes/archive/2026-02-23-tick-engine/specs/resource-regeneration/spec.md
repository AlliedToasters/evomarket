## ADDED Requirements

### Requirement: Resource nodes accumulate resources each tick
`regenerate_resources(world: WorldState)` SHALL add `resource_spawn_rate * distribution[commodity]` to each commodity's stockpile at every RESOURCE-type node, each tick.

#### Scenario: Resource accumulates at spawn rate
- **WHEN** a resource node has spawn_rate=0.5 and iron distribution=0.8
- **THEN** iron stockpile increases by 0.4 per tick

#### Scenario: Non-resource nodes are skipped
- **WHEN** a node is TRADE_HUB or SPAWN type
- **THEN** no resources are added to its stockpile

### Requirement: Resource stockpile capped at resource_cap
Resource stockpiles SHALL NOT exceed the node's `resource_cap`. Accumulation stops when the cap is reached for a given commodity.

#### Scenario: Stockpile at cap does not increase
- **WHEN** iron stockpile is 20.0 and resource_cap is 20
- **THEN** iron stockpile remains 20.0 after regeneration

#### Scenario: Stockpile approaching cap is clamped
- **WHEN** iron stockpile is 19.8, spawn_rate * distribution = 0.4, and resource_cap is 20
- **THEN** iron stockpile becomes 20.0 (clamped), not 20.2

### Requirement: Fractional accumulation
Resource stockpiles SHALL support fractional values. A spawn rate of 0.5 means one full unit appears every 2 ticks.

#### Scenario: Fractional accumulation over two ticks
- **WHEN** iron stockpile starts at 0.0, spawn_rate=0.5, and distribution=1.0
- **THEN** after 1 tick stockpile is 0.5 (not harvestable), after 2 ticks stockpile is 1.0 (1 unit harvestable)
