## Why

There is no way to visualize the spatial structure of the economy — where agents are, how nodes connect, or how wealth distributes across the world graph. Understanding agent movement patterns, resource clustering, and spatial trade dynamics requires seeing the topology. The world graph is central to EvoMarket's design (clustered resource nodes, trade hubs, spawn points), but analysis is currently blind to spatial relationships.

## What Changes

- Add a new Streamlit panel (`visualization/panels/spatial_graph.py`) that renders the world graph using NetworkX for layout and Plotly for interactive display
- Nodes colored by `NodeType` (RESOURCE, TRADE_HUB, SPAWN) using existing `NODE_TYPE_COLORS` palette
- Agents rendered as dots at their current node, sized by wealth (credits)
- Tick slider to scrub through simulation time, updating agent positions and sizes
- Hover tooltips showing node-level stats (resource stockpile, NPC budget, agent count, node type) and agent-level stats (ID, credits, inventory, age)
- Add a `load_graph_topology()` function to `visualization/data.py` that reconstructs the world graph from `config.json`
- Register the panel in `visualization/app.py`

## Capabilities

### New Capabilities
- `viz-spatial-panel`: Interactive spatial graph visualization panel with time-scrubbing, node/agent rendering, and hover stats

### Modified Capabilities
- `viz-data-layer`: Add `load_graph_topology()` function to reconstruct node graph (adjacency, types, resource distributions) from episode config

## Impact

- **New file**: `visualization/panels/spatial_graph.py` — the panel implementation
- **Modified file**: `visualization/data.py` — add graph topology loading
- **Modified file**: `visualization/app.py` — uncomment/add panel import
- **Dependencies**: Uses existing `networkx`, `plotly`, `streamlit` packages (all already in pyproject.toml)
- **Data sources**: `config.json` (world config + seed), `agent_snapshots` table (agent positions/credits per tick)
