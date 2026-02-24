## ADDED Requirements

### Requirement: Panel registration
The system SHALL register an "Agent Wealth Trajectories" panel with the app shell via `register_panel()` so it appears in sidebar navigation.

#### Scenario: Panel appears in sidebar
- **WHEN** `visualization/panels/agent_trajectories.py` is imported
- **THEN** the panel SHALL be registered with name "Agent Wealth Trajectories" and appear in sidebar navigation

### Requirement: Wealth trajectory chart
The system SHALL render a multi-line Altair chart showing each agent's credit balance over time, with one line per agent.

#### Scenario: Lines drawn per agent
- **WHEN** the panel renders with agent snapshot data
- **THEN** each agent SHALL have its own line plotting credits (y-axis) against tick (x-axis)

#### Scenario: Lines colored by agent type
- **WHEN** the chart renders
- **THEN** each agent's line SHALL be colored according to `AGENT_TYPE_COLORS` based on the agent's type (harvester, trader, social, hoarder, explorer, random)

#### Scenario: Legend shows agent types
- **WHEN** the chart renders
- **THEN** the color legend SHALL show agent type names (not individual agent IDs)

#### Scenario: Empty snapshot data
- **WHEN** `load_agent_snapshots` returns an empty DataFrame
- **THEN** the panel SHALL display a warning message instead of crashing

### Requirement: Tick range filtering
The system SHALL provide a tick range slider that filters the wealth trajectory chart to the selected tick range.

#### Scenario: Slider filters chart data
- **WHEN** the user adjusts the tick range slider to [50, 200]
- **THEN** the chart SHALL only show data for ticks 50 through 200

### Requirement: Agent filter
The system SHALL provide an agent multiselect widget that filters which agents are shown in the trajectory chart.

#### Scenario: Filter to specific agents
- **WHEN** the user selects agents ["agent_001", "agent_003"]
- **THEN** the chart SHALL only show lines for those agents

#### Scenario: No selection shows all agents
- **WHEN** the user leaves the agent filter empty
- **THEN** the chart SHALL show lines for all agents

### Requirement: Agent summary table
The system SHALL render a sortable table showing per-agent summary statistics below the trajectory chart.

#### Scenario: Table columns
- **WHEN** the table renders
- **THEN** it SHALL display columns: agent_id, agent_type, net_worth, lifetime, total_trades, final_credits, cause_of_death

#### Scenario: Default sort by net worth
- **WHEN** the table first renders
- **THEN** rows SHALL be sorted by net_worth descending

#### Scenario: User sorts by column
- **WHEN** the user clicks a column header
- **THEN** the table SHALL re-sort by that column

#### Scenario: No result data
- **WHEN** `result.json` is missing or has no agent_summaries
- **THEN** the panel SHALL display a warning message instead of the table

### Requirement: Render function signature
The panel's render function SHALL accept a single `episode_dir: str` argument matching the app shell's panel contract.

#### Scenario: Render function called by app shell
- **WHEN** the app shell selects the Agent Wealth Trajectories panel
- **THEN** it SHALL call `render(episode_dir)` where `episode_dir` is the path to the episode output directory
