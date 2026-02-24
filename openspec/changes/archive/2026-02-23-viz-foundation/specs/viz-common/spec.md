## ADDED Requirements

### Requirement: Commodity color palette
The system SHALL provide a dict `COMMODITY_COLORS` mapping each commodity type string to a distinct hex color: IRON, WOOD, STONE, HERBS.

#### Scenario: All commodities have colors
- **WHEN** a panel accesses `COMMODITY_COLORS`
- **THEN** it SHALL contain entries for "IRON", "WOOD", "STONE", "HERBS" with distinct hex color values

#### Scenario: Colors are visually distinct
- **WHEN** the four commodity colors are rendered
- **THEN** they SHALL be visually distinguishable (e.g., IRON=gray, WOOD=brown, STONE=slate, HERBS=green)

### Requirement: Agent type color palette
The system SHALL provide a dict `AGENT_TYPE_COLORS` mapping each agent type string to a distinct hex color: harvester, trader, social, hoarder, explorer, random.

#### Scenario: All agent types have colors
- **WHEN** a panel accesses `AGENT_TYPE_COLORS`
- **THEN** it SHALL contain entries for "harvester", "trader", "social", "hoarder", "explorer", "random"

### Requirement: Node type color palette
The system SHALL provide a dict `NODE_TYPE_COLORS` mapping each node type string to a distinct hex color: RESOURCE, TRADE_HUB, SPAWN.

#### Scenario: All node types have colors
- **WHEN** a panel accesses `NODE_TYPE_COLORS`
- **THEN** it SHALL contain entries for "RESOURCE", "TRADE_HUB", "SPAWN" with distinct hex color values

### Requirement: Tick range selector widget
The system SHALL provide a function `tick_range_selector(max_tick: int, key: str) -> tuple[int, int]` that renders a Streamlit slider for selecting a tick range and returns the selected `(start_tick, end_tick)` tuple.

#### Scenario: Default range is full episode
- **WHEN** `tick_range_selector(max_tick=499, key="ts")` is called
- **THEN** it SHALL render a range slider with default values `(0, 499)`

#### Scenario: User adjusts range
- **WHEN** the user drags the slider handles
- **THEN** the function SHALL return the updated `(start_tick, end_tick)` values

### Requirement: Agent filter widget
The system SHALL provide a function `agent_filter(agent_ids: list[str], key: str) -> list[str]` that renders a Streamlit multiselect for filtering agents and returns the selected agent IDs. If no agents are selected, it SHALL return the full list (i.e., no filter).

#### Scenario: No selection means all agents
- **WHEN** the user leaves the multiselect empty
- **THEN** the function SHALL return the full `agent_ids` list

#### Scenario: User selects specific agents
- **WHEN** the user selects agents ["agent_001", "agent_003"]
- **THEN** the function SHALL return `["agent_001", "agent_003"]`

### Requirement: Commodity selector widget
The system SHALL provide a function `commodity_selector(key: str) -> list[str]` that renders a Streamlit multiselect with all four commodity types and returns the selected commodities. If none selected, returns all.

#### Scenario: Default returns all commodities
- **WHEN** the user leaves the multiselect empty
- **THEN** the function SHALL return `["IRON", "WOOD", "STONE", "HERBS"]`

### Requirement: Millicredit formatting helper
The system SHALL provide a function `format_credits(mc_value: int) -> str` that converts a millicredit integer to a formatted display credit string (e.g., 50000 → "50.00").

#### Scenario: Format millicredits
- **WHEN** `format_credits(50000)` is called
- **THEN** it SHALL return `"50.00"`

#### Scenario: Format zero
- **WHEN** `format_credits(0)` is called
- **THEN** it SHALL return `"0.00"`
