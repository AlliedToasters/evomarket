### Requirement: Panel registration
The time series panel module SHALL register itself with the app shell by calling `register_panel("Time Series", render)` at module import time. The render function SHALL accept an `episode_dir: str` parameter.

#### Scenario: Panel appears in sidebar
- **WHEN** `visualization.panels.time_series` is imported in `app.py`
- **THEN** "Time Series" appears as a selectable panel in the sidebar navigation

### Requirement: Tick range filtering
The panel SHALL display a tick range selector (using `common.tick_range_selector`) that filters all five sub-charts to the selected range.

#### Scenario: User narrows tick range
- **WHEN** the user adjusts the tick range slider to ticks 50–200
- **THEN** all five sub-charts display data only for ticks 50 through 200

### Requirement: Credit reservoirs stacked area chart
The panel SHALL display a stacked area chart showing how the fixed credit supply is distributed between agents and the system (NPC budgets + treasury) over time. Agent credits SHALL be computed by summing `credits` from `load_agent_snapshots()` grouped by tick. System credits SHALL be `total_credit_supply - agent_credits` using the total supply from `load_config()`.

#### Scenario: Stacked area sums to total supply
- **WHEN** the credit reservoirs chart renders for any tick
- **THEN** the two stacked areas (agent credits, system credits) sum to the configured `total_credit_supply` (converted to display credits)

#### Scenario: Empty snapshots
- **WHEN** `load_agent_snapshots()` returns an empty DataFrame (no agents present)
- **THEN** the chart shows the full credit supply allocated to the system reservoir

### Requirement: Population count line chart
The panel SHALL display a line chart of `agents_alive` from `load_tick_metrics()` over time.

#### Scenario: Population displayed
- **WHEN** the panel renders with tick metrics data
- **THEN** a line chart shows the number of living agents at each tick

### Requirement: Gini coefficient line chart
The panel SHALL display a line chart of `agent_credit_gini` from `load_tick_metrics()` over time. The y-axis range SHALL be 0 to 1.

#### Scenario: Gini displayed with fixed axis
- **WHEN** the panel renders with tick metrics data
- **THEN** a line chart shows the Gini coefficient at each tick with y-axis spanning 0 to 1

### Requirement: Deaths per tick bar chart
The panel SHALL display a bar chart of `agents_died` from `load_tick_metrics()` over time.

#### Scenario: Deaths displayed
- **WHEN** the panel renders with tick metrics data
- **THEN** a bar chart shows the number of agent deaths at each tick

### Requirement: Trade volume line chart
The panel SHALL display a line chart of `total_trade_volume` from `load_tick_metrics()` over time. Values are in display credits (already converted by the data layer).

#### Scenario: Trade volume displayed
- **WHEN** the panel renders with tick metrics data
- **THEN** a line chart shows the total trade volume in display credits at each tick

### Requirement: Chart layout
All five sub-charts SHALL be rendered vertically stacked in a single scrollable panel, each using the full container width. The order from top to bottom SHALL be: credit reservoirs, population, Gini coefficient, deaths per tick, trade volume.

#### Scenario: Chart ordering
- **WHEN** the panel renders
- **THEN** the five charts appear in order: credit reservoirs, population, Gini, deaths, trade volume
