## ADDED Requirements

### Requirement: Database connection management
The system SHALL provide a function to open a read-only SQLite connection to an episode database, cached via `st.cache_resource` so that only one connection exists per database path per Streamlit session.

#### Scenario: Connection opened successfully
- **WHEN** `get_connection(db_path)` is called with a valid SQLite database path
- **THEN** it SHALL return a `sqlite3.Connection` in WAL mode

#### Scenario: Connection is cached
- **WHEN** `get_connection(db_path)` is called twice with the same path
- **THEN** it SHALL return the same connection object

### Requirement: Tick metrics query
The system SHALL provide a function that returns a DataFrame of per-tick metrics from the `ticks` table, with the `metrics_json` column unpacked into individual columns. Credit-denominated metrics SHALL be converted from millicredits to display credits.

#### Scenario: Load all tick metrics
- **WHEN** `load_tick_metrics(db_path)` is called
- **THEN** it SHALL return a DataFrame with columns: `tick`, `total_credits_in_circulation`, `agent_credit_gini`, `total_trade_volume`, `trades_executed`, `agents_alive`, `agents_died`, `agents_spawned`, `total_resources_harvested`, `total_npc_sales`, `total_messages_sent`
- **AND** `total_credits_in_circulation` and `total_trade_volume` SHALL be in display credits (divided by 1000)

#### Scenario: Result is cached
- **WHEN** `load_tick_metrics(db_path)` is called multiple times with the same path
- **THEN** it SHALL return cached results via `st.cache_data`

### Requirement: Agent snapshots query
The system SHALL provide a function that returns a DataFrame of per-agent-per-tick snapshots from the `agent_snapshots` table, with `inventory_json` unpacked and credits converted to display credits.

#### Scenario: Load all agent snapshots
- **WHEN** `load_agent_snapshots(db_path)` is called
- **THEN** it SHALL return a DataFrame with columns: `tick`, `agent_id`, `credits`, `inventory_IRON`, `inventory_WOOD`, `inventory_STONE`, `inventory_HERBS`, `location`, `age`
- **AND** `credits` SHALL be in display credits

### Requirement: Trades query
The system SHALL provide a function that returns a DataFrame of all trades from the `trades` table, with credits converted to display credits.

#### Scenario: Load all trades
- **WHEN** `load_trades(db_path)` is called
- **THEN** it SHALL return a DataFrame with columns: `tick`, `buyer_id`, `seller_id`, `trade_type`, `credits`
- **AND** `credits` SHALL be in display credits

### Requirement: Deaths query
The system SHALL provide a function that returns a DataFrame of all deaths from the `deaths` table, with `estate_json` unpacked and credits converted.

#### Scenario: Load all deaths
- **WHEN** `load_deaths(db_path)` is called
- **THEN** it SHALL return a DataFrame with columns: `tick`, `agent_id`, `estate_credits`, `estate_IRON`, `estate_WOOD`, `estate_STONE`, `estate_HERBS`
- **AND** `estate_credits` SHALL be in display credits

### Requirement: Actions query
The system SHALL provide a function that returns a DataFrame of all actions from the `actions` table.

#### Scenario: Load all actions
- **WHEN** `load_actions(db_path)` is called
- **THEN** it SHALL return a DataFrame with columns: `tick`, `agent_id`, `action_type`, `success`, `detail`

### Requirement: Messages query
The system SHALL provide a function that returns a DataFrame of all messages from the `messages` table.

#### Scenario: Load all messages
- **WHEN** `load_messages(db_path)` is called
- **THEN** it SHALL return a DataFrame with columns: `tick`, `sender_id`, `recipient`, `text`

### Requirement: Episode config loading
The system SHALL provide a function that loads and returns the `config.json` file from the episode directory as a dict.

#### Scenario: Load config
- **WHEN** `load_config(episode_dir)` is called with a directory containing `config.json`
- **THEN** it SHALL return the parsed JSON as a Python dict

### Requirement: Episode result loading
The system SHALL provide a function that loads `result.json` from the episode directory, including agent summaries.

#### Scenario: Load result
- **WHEN** `load_result(episode_dir)` is called with a directory containing `result.json`
- **THEN** it SHALL return the parsed JSON as a Python dict

### Requirement: Agent type mapping
The system SHALL provide a function that returns a mapping from `agent_id` to `agent_type` string, derived from `result.json` agent summaries.

#### Scenario: Get agent types
- **WHEN** `load_agent_types(episode_dir)` is called
- **THEN** it SHALL return a dict mapping each agent_id to its agent_type string (e.g., "harvester", "trader")

### Requirement: Agent summaries query
The system SHALL provide a function `load_agent_summaries(episode_dir: str) -> pd.DataFrame` that loads agent summary data from `result.json` and returns it as a DataFrame.

#### Scenario: Load agent summaries
- **WHEN** `load_agent_summaries(episode_dir)` is called with a directory containing `result.json`
- **THEN** it SHALL return a DataFrame with columns: `agent_id`, `agent_type`, `net_worth`, `lifetime`, `total_trades`, `final_credits`, `cause_of_death`

#### Scenario: Agent type normalization
- **WHEN** `result.json` contains agent_type values like "HarvesterAgent"
- **THEN** the function SHALL normalize them to short names (e.g., "harvester") matching `AGENT_TYPE_COLORS` keys

#### Scenario: Credit conversion
- **WHEN** the function reads credit values from `result.json`
- **THEN** `net_worth` and `final_credits` SHALL be converted from millicredits to display credits (divided by 1000)

#### Scenario: Result is cached
- **WHEN** `load_agent_summaries(episode_dir)` is called multiple times with the same path
- **THEN** it SHALL return cached results via `st.cache_data`

#### Scenario: Missing result file
- **WHEN** `result.json` does not exist at the given path
- **THEN** the function SHALL return an empty DataFrame with the expected columns

### Requirement: All query functions use st.cache_data
Every DataFrame-returning query function SHALL be decorated with `@st.cache_data` to avoid re-executing SQL queries on Streamlit reruns.

#### Scenario: Cache invalidation on different db_path
- **WHEN** a query function is called with a different `db_path` than a previous call
- **THEN** it SHALL execute the query fresh and cache the new result
