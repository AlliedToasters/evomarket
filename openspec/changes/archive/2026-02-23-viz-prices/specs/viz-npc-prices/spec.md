## ADDED Requirements

### Requirement: NPC Prices panel registration
The system SHALL provide a visualization panel named "NPC Prices" that registers itself with the app shell via `register_panel("NPC Prices", render)`.

#### Scenario: Panel appears in sidebar
- **WHEN** the NPC prices panel module is imported in `app.py`
- **THEN** "NPC Prices" SHALL appear as a selectable panel in the sidebar navigation

### Requirement: Render function accepts episode directory
The panel render function SHALL accept `episode_dir: str` as its sole argument, consistent with the app shell contract.

#### Scenario: Panel invoked by app shell
- **WHEN** the user selects "NPC Prices" and a valid episode is loaded
- **THEN** the app shell SHALL call `render(episode_dir)` and the panel SHALL display without errors

### Requirement: Graceful handling of missing NPC data
The panel SHALL detect whether the `npc_snapshots` table exists in the episode database. If absent, it SHALL display an informative message instead of crashing.

#### Scenario: Old episode without npc_snapshots table
- **WHEN** the panel loads an episode whose database lacks the `npc_snapshots` table
- **THEN** the panel SHALL display a message stating that NPC price data is not available for this episode

#### Scenario: Episode with npc_snapshots table
- **WHEN** the panel loads an episode whose database contains the `npc_snapshots` table with data
- **THEN** the panel SHALL render the heatmap and controls normally

### Requirement: Commodity tab selection
The panel SHALL display one heatmap per commodity type using Streamlit tabs. Each tab SHALL be labeled with the commodity name (e.g., "IRON", "WOOD", "STONE", "HERBS").

#### Scenario: Four commodity tabs displayed
- **WHEN** the episode has NPC snapshot data for all four commodity types
- **THEN** the panel SHALL display four tabs, one per commodity

#### Scenario: Subset of commodities
- **WHEN** the episode has NPC snapshot data for only 2 commodity types
- **THEN** the panel SHALL display only tabs for commodities present in the data

### Requirement: Price heatmap grid
Each commodity tab SHALL display a Plotly heatmap with nodes on the y-axis, ticks on the x-axis, and color intensity representing price. Only nodes that buy the given commodity SHALL appear on the y-axis.

#### Scenario: Heatmap axes and data
- **WHEN** the "IRON" tab is selected and 5 nodes buy IRON over 500 ticks
- **THEN** the heatmap SHALL display a 5-row by 500-column grid where each cell's color represents the NPC price for that node at that tick

#### Scenario: Color scale
- **WHEN** the heatmap is rendered for a commodity
- **THEN** the color scale SHALL use the commodity's color from `COMMODITY_COLORS` as the high end, with white/light as the low end

### Requirement: Tick range filtering
The panel SHALL include a tick range selector (using `tick_range_selector` from `viz-common`) that filters the heatmap x-axis to the selected range.

#### Scenario: User narrows tick range
- **WHEN** the user adjusts the tick range slider to ticks 100-300
- **THEN** the heatmap SHALL display only ticks 100 through 300

### Requirement: Node selection for price curves
The panel SHALL include a node selectbox. When a node is selected, a line chart SHALL display that node's NPC price over time for all commodities the node buys.

#### Scenario: Node selected shows price curve
- **WHEN** the user selects "node_hub_iron" from the selectbox
- **THEN** a line chart SHALL appear showing price vs. tick for each commodity that node buys, with lines colored per `COMMODITY_COLORS`

#### Scenario: No node selected
- **WHEN** no node is selected (or default placeholder)
- **THEN** no price curve chart SHALL be displayed

### Requirement: Heatmap hover tooltip
Each cell in the heatmap SHALL show a tooltip on hover containing the node name, tick number, and price value (in display credits).

#### Scenario: User hovers over heatmap cell
- **WHEN** the user hovers over a cell at node "node_hub_iron", tick 42
- **THEN** a tooltip SHALL display the node name, tick number, and price formatted in display credits
