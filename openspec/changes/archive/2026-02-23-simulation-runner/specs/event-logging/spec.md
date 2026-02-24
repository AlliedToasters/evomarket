## ADDED Requirements

### Requirement: SQLite event database
The `EventLogger` SHALL create a SQLite database with 6 tables: `ticks`, `actions`, `trades`, `deaths`, `messages`, and `agent_snapshots`.

#### Scenario: Database created on init
- **WHEN** an `EventLogger` is initialized with an output path
- **THEN** a SQLite database is created with all 6 tables and correct schemas

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

### Requirement: Disableable logging
The `EventLogger` SHALL support a no-op mode where all logging calls are silently ignored, for use in hyperfast mode.

#### Scenario: No-op logger
- **WHEN** `EventLogger(enabled=False)` is constructed
- **THEN** all `log_*` calls are no-ops and no database file is created
