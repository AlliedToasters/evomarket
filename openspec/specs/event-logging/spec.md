## ADDED Requirements

### Requirement: SQLite event database
The `EventLogger` SHALL create a SQLite database with 7 tables: `ticks`, `actions`, `trades`, `deaths`, `messages`, `agent_snapshots`, and `npc_snapshots`.

#### Scenario: Database created on init
- **WHEN** an `EventLogger` is initialized with an output path
- **THEN** a SQLite database is created with all 7 tables and correct schemas

### Requirement: Tick logging
The `ticks` table SHALL record one row per tick with: `tick_number` (INTEGER PRIMARY KEY), `timestamp` (TEXT), and `metrics_json` (TEXT) containing the serialized `TickMetrics`.

#### Scenario: Tick recorded
- **WHEN** `logger.log_tick(tick_number, tick_metrics)` is called
- **THEN** a row is inserted into the `ticks` table with the tick's metrics as JSON

### Requirement: Action logging
The `actions` table SHALL record one row per agent action per tick with: `tick` (INTEGER), `agent_id` (TEXT), `action_type` (TEXT), `action_json` (TEXT), `success` (INTEGER), `detail` (TEXT).

#### Scenario: Action recorded
- **WHEN** `logger.log_actions(tick, action_results)` is called
- **THEN** one row per action result is inserted into the `actions` table

### Requirement: Trade logging
The `trades` table SHALL record one row per executed trade with: `tick` (INTEGER), `buyer_id` (TEXT), `seller_id` (TEXT), `trade_type` (TEXT: "order" or "p2p"), `items_json` (TEXT), `credits` (INTEGER).

#### Scenario: Trade recorded
- **WHEN** a trade executes (accept_order or accept_trade) with success=True
- **THEN** a row is inserted into the `trades` table

### Requirement: Death logging
The `deaths` table SHALL record one row per agent death with: `tick` (INTEGER), `agent_id` (TEXT), `estate_json` (TEXT), `will_json` (TEXT).

#### Scenario: Death recorded
- **WHEN** an agent dies
- **THEN** a row is inserted into the `deaths` table with the agent's estate and will at time of death

### Requirement: Message logging
The `messages` table SHALL record one row per message sent with: `tick` (INTEGER), `sender_id` (TEXT), `recipient` (TEXT), `node_id` (TEXT), `text` (TEXT).

#### Scenario: Message recorded
- **WHEN** an agent sends a message (direct or broadcast)
- **THEN** a row is inserted into the `messages` table

### Requirement: Agent snapshot logging
The `agent_snapshots` table SHALL record one row per living agent per tick with: `tick` (INTEGER), `agent_id` (TEXT), `credits` (INTEGER), `inventory_json` (TEXT), `location` (TEXT), `age` (INTEGER).

#### Scenario: Snapshots recorded per tick
- **WHEN** a tick completes with 15 living agents
- **THEN** 15 rows are inserted into the `agent_snapshots` table

### Requirement: Batched writes
All event inserts for a single tick SHALL be batched into a single SQLite transaction for performance.

#### Scenario: Single transaction per tick
- **WHEN** `logger.flush_tick()` is called
- **THEN** all buffered events are committed in a single transaction

### Requirement: WAL mode
The `EventLogger` SHALL open the SQLite database in WAL (Write-Ahead Logging) mode for concurrent read access during writes.

#### Scenario: WAL mode enabled
- **WHEN** the database is opened
- **THEN** `PRAGMA journal_mode=WAL` is set

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

### Requirement: Disableable logging
The `EventLogger` SHALL support a no-op mode where all logging calls are silently ignored, for use in hyperfast mode.

#### Scenario: No-op logger
- **WHEN** `EventLogger(enabled=False)` is constructed
- **THEN** all `log_*` calls are no-ops and no database file is created
