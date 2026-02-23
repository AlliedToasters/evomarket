## ADDED Requirements

### Requirement: NPC budget distribution config
`WorldConfig` SHALL include a `npc_budget_distribution: str` field with default value `"equal"`, controlling how replenishment credits are split across NPC nodes.

#### Scenario: Default distribution mode
- **WHEN** a `WorldConfig` is created without specifying `npc_budget_distribution`
- **THEN** the value defaults to `"equal"`

### Requirement: Treasury minimum reserve config
`WorldConfig` SHALL include a `treasury_min_reserve: Millicredits` field with default value `100_000` (100 display credits), representing the minimum treasury balance below which NPC budget replenishment is suspended.

#### Scenario: Default minimum reserve
- **WHEN** a `WorldConfig` is created without specifying `treasury_min_reserve`
- **THEN** the value defaults to `100_000` millicredits
