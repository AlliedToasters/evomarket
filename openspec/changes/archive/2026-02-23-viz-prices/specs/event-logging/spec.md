## ADDED Requirements

### Requirement: NPC snapshot table
The `EventLogger` SHALL create an `npc_snapshots` table with columns: `tick` (INTEGER), `node_id` (TEXT), `commodity` (TEXT), `price` (INTEGER), `stockpile` (INTEGER), `budget` (INTEGER). An index SHALL be created on the `tick` column.

#### Scenario: Table created on init
- **WHEN** an `EventLogger` is initialized with an output path
- **THEN** the database SHALL contain the `npc_snapshots` table with the specified schema and an index on `tick`

### Requirement: NPC snapshot logging
The `EventLogger` SHALL provide a `log_npc_snapshots(tick: int, world: WorldState)` method that buffers one row per (node, commodity) pair for every commodity the node buys. Each row SHALL contain the current NPC price (from `world.get_npc_price`), stockpile, and budget at that node.

#### Scenario: Snapshots buffered for all NPC nodes
- **WHEN** `log_npc_snapshots(tick=5, world)` is called and the world has 3 nodes buying 2 commodities each
- **THEN** 6 rows SHALL be buffered for the `npc_snapshots` table

#### Scenario: Non-NPC nodes excluded
- **WHEN** `log_npc_snapshots` is called and a node has an empty `npc_buys` list
- **THEN** no rows SHALL be buffered for that node

#### Scenario: No-op when disabled
- **WHEN** `log_npc_snapshots` is called on an `EventLogger(enabled=False)`
- **THEN** no rows SHALL be buffered

## MODIFIED Requirements

### Requirement: SQLite event database
The `EventLogger` SHALL create a SQLite database with 7 tables: `ticks`, `actions`, `trades`, `deaths`, `messages`, `agent_snapshots`, and `npc_snapshots`.

#### Scenario: Database created on init
- **WHEN** an `EventLogger` is initialized with an output path
- **THEN** a SQLite database is created with all 7 tables and correct schemas
