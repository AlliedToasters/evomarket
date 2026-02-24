## ADDED Requirements

### Requirement: NPC snapshots query
The system SHALL provide a function that returns a DataFrame of per-node-per-tick NPC state from the `npc_snapshots` table, with prices and budgets converted from millicredits to display credits.

#### Scenario: Load all NPC snapshots
- **WHEN** `load_npc_snapshots(db_path)` is called on a database containing the `npc_snapshots` table
- **THEN** it SHALL return a DataFrame with columns: `tick`, `node_id`, `commodity`, `price`, `stockpile`, `budget`
- **AND** `price` and `budget` SHALL be in display credits (divided by 1000)

#### Scenario: Result is cached
- **WHEN** `load_npc_snapshots(db_path)` is called multiple times with the same path
- **THEN** it SHALL return cached results via `@st.cache_data`

### Requirement: NPC snapshots table existence check
The system SHALL provide a function that checks whether the `npc_snapshots` table exists in the episode database.

#### Scenario: Table exists
- **WHEN** `has_npc_snapshots(db_path)` is called on a database containing the `npc_snapshots` table
- **THEN** it SHALL return `True`

#### Scenario: Table missing
- **WHEN** `has_npc_snapshots(db_path)` is called on a database without the `npc_snapshots` table
- **THEN** it SHALL return `False`
