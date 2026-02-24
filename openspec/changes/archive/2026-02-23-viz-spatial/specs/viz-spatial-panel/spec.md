## ADDED Requirements

### Requirement: Panel registration
The system SHALL provide a spatial graph panel registered with the app shell via `register_panel("Spatial Graph", render_spatial_graph)` in `visualization/panels/spatial_graph.py`.

#### Scenario: Panel appears in sidebar
- **WHEN** the spatial graph panel module is imported in `app.py`
- **THEN** "Spatial Graph" SHALL appear in the sidebar navigation

#### Scenario: Panel renders without error
- **WHEN** the user selects "Spatial Graph" and a valid episode directory is loaded
- **THEN** the panel SHALL render a graph visualization without errors

### Requirement: Graph topology display
The panel SHALL render the world graph with nodes positioned using `networkx.spring_layout()` and edges drawn between adjacent nodes.

#### Scenario: All nodes visible
- **WHEN** the panel renders for an episode with 15 nodes
- **THEN** all 15 nodes SHALL be visible as markers on the plot

#### Scenario: All edges visible
- **WHEN** node A is adjacent to node B in the world graph
- **THEN** a line SHALL be drawn between their positions on the plot

#### Scenario: Layout is stable
- **WHEN** the user changes the tick slider and returns to the original tick
- **THEN** node positions SHALL remain identical (layout is computed once and cached)

### Requirement: Node coloring by type
Nodes SHALL be colored according to their `NodeType` using the `NODE_TYPE_COLORS` palette from `visualization/common.py`: RESOURCE (green), TRADE_HUB (orange), SPAWN (blue).

#### Scenario: Resource nodes are green
- **WHEN** the graph renders
- **THEN** all RESOURCE nodes SHALL use the color from `NODE_TYPE_COLORS["RESOURCE"]`

#### Scenario: Trade hub nodes are orange
- **WHEN** the graph renders
- **THEN** all TRADE_HUB nodes SHALL use the color from `NODE_TYPE_COLORS["TRADE_HUB"]`

#### Scenario: Spawn nodes are blue
- **WHEN** the graph renders
- **THEN** the SPAWN node SHALL use the color from `NODE_TYPE_COLORS["SPAWN"]`

### Requirement: Node labels
Each node SHALL display its `name` as a text label on or near the marker.

#### Scenario: Node names shown
- **WHEN** the graph renders
- **THEN** each node marker SHALL have a visible text label with the node's name

### Requirement: Agent rendering as dots
Living agents at the current tick SHALL be rendered as circular markers positioned at their current node's location.

#### Scenario: Agents shown at correct node
- **WHEN** agent_001 is at node_iron_0 at tick 50
- **THEN** agent_001's marker SHALL be positioned at node_iron_0's graph coordinates

#### Scenario: Only living agents shown
- **WHEN** agent_003 died at tick 30 and the current tick is 50
- **THEN** agent_003 SHALL NOT appear on the graph

### Requirement: Agent marker size by wealth
Agent markers SHALL be sized proportionally to their credit balance. Wealthier agents SHALL have larger markers.

#### Scenario: Wealthy agent has larger marker
- **WHEN** agent_001 has 100 credits and agent_002 has 10 credits at the current tick
- **THEN** agent_001's marker SHALL be visibly larger than agent_002's

#### Scenario: Minimum marker size
- **WHEN** an agent has 0 credits
- **THEN** the agent's marker SHALL still be visible (minimum marker size enforced)

### Requirement: Agent jitter for co-located agents
When multiple agents occupy the same node, their markers SHALL be offset with small deterministic jitter around the node center so all agents remain individually visible.

#### Scenario: Two agents at same node
- **WHEN** two agents are at the same node
- **THEN** their markers SHALL be at slightly different positions (not stacked)

#### Scenario: Jitter is deterministic
- **WHEN** the same tick is viewed multiple times
- **THEN** agent positions within a node SHALL remain consistent

### Requirement: Tick slider
The panel SHALL provide a single-value `st.slider` allowing the user to select any tick in the episode. The graph SHALL update to show agent positions and stats at the selected tick.

#### Scenario: Slider range matches episode
- **WHEN** the episode has 500 ticks
- **THEN** the slider SHALL range from 0 to 499

#### Scenario: Changing tick updates agents
- **WHEN** the user moves the slider from tick 10 to tick 50
- **THEN** agent positions and marker sizes SHALL update to reflect tick 50 state

#### Scenario: Nodes remain fixed across ticks
- **WHEN** the user changes the tick
- **THEN** node positions and edges SHALL NOT change (only agent overlay updates)

### Requirement: Node hover stats
Hovering over a node marker SHALL display a tooltip with node-level statistics.

#### Scenario: Node tooltip content
- **WHEN** the user hovers over a RESOURCE node
- **THEN** the tooltip SHALL show: node name, node type, number of agents currently at the node, total wealth of agents at the node, and the node's primary resource type

#### Scenario: Trade hub tooltip
- **WHEN** the user hovers over a TRADE_HUB node
- **THEN** the tooltip SHALL show: node name, node type, number of agents, total wealth, and commodities the NPC buys

### Requirement: Agent hover stats
Hovering over an agent marker SHALL display a tooltip with agent-level statistics.

#### Scenario: Agent tooltip content
- **WHEN** the user hovers over an agent marker
- **THEN** the tooltip SHALL show: agent_id, credits (formatted as display credits), inventory counts for each commodity, age (ticks survived), and current location

### Requirement: Legend
The plot SHALL include a legend distinguishing node types by color and indicating that agent marker size represents wealth.

#### Scenario: Node type legend
- **WHEN** the graph renders
- **THEN** the legend SHALL show entries for RESOURCE, TRADE_HUB, and SPAWN with their respective colors
