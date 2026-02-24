## Context

The EvoMarket visualization dashboard has an established panel architecture (app shell, data layer, common utilities) but no panels yet. The world is a graph of 15+ nodes (RESOURCE, TRADE_HUB, SPAWN) with agents moving between them each tick. Agent snapshots (location, credits, inventory) are logged per tick to SQLite. The graph topology is deterministic from config + seed but not directly stored in the database.

Existing infrastructure:
- `visualization/app.py` — panel registry with `register_panel()`
- `visualization/data.py` — cached SQLite queries (`load_agent_snapshots`, `load_config`, etc.)
- `visualization/common.py` — `NODE_TYPE_COLORS`, `COMMODITY_COLORS`, `tick_range_selector`, `format_credits`
- Dependencies: `networkx`, `plotly`, `streamlit` all in pyproject.toml

## Goals / Non-Goals

**Goals:**
- Render the world graph with nodes colored by type and edges showing connectivity
- Show agents as dots at their current node, sized by wealth
- Provide a tick slider to scrub through time and see agent movement
- Display node-level and agent-level stats on hover
- Integrate cleanly with the existing panel architecture and data layer

**Non-Goals:**
- Animated transitions between ticks (static re-render per tick is sufficient)
- Editable graph layout (layout is computed once and cached)
- Real-time streaming from a running simulation (replay from SQLite only)
- Edge-level metrics (trade flow visualization between nodes)
- 3D visualization

## Decisions

### 1. Graph layout: NetworkX spring layout, computed once and cached

Use `networkx.spring_layout()` to compute 2D coordinates for all nodes. The layout is computed once per episode and cached with `@st.cache_data`, since the graph topology is static across all ticks.

**Why spring layout**: Naturally clusters connected nodes together, which mirrors the clustered resource topology. Trade hubs end up central to their clusters. No external dependencies beyond networkx (already available).

**Alternative considered**: `kamada_kawai_layout` produces more uniform spacing but is slower and doesn't emphasize cluster structure as well. `graphviz` layouts require an external binary.

### 2. Rendering: Plotly scatter + line traces on a single figure

Render the graph as a Plotly `Figure` with:
- **Edge traces**: One `Scatter` trace with lines connecting adjacent nodes (using `None` separators for disconnected segments)
- **Node traces**: One `Scatter` trace per `NodeType`, colored by `NODE_TYPE_COLORS`, with hover text showing node stats
- **Agent traces**: One `Scatter` trace for agents at the current tick, with marker size proportional to credits and hover text showing agent stats

**Why Plotly**: Already a dependency. Native Streamlit support via `st.plotly_chart`. Hover tooltips are built-in. No additional JS/widget packages needed.

**Alternative considered**: `streamlit-agraph` provides a dedicated graph widget but adds a dependency and is less flexible for custom styling. Cytoscape.js via `st.components` would require HTML/JS embedding.

### 3. Agent positioning: Jitter around node center

When multiple agents occupy the same node, position them with small random offsets (jitter) around the node's layout coordinates. Use a deterministic jitter based on agent index to keep positions stable across re-renders of the same tick.

**Why jitter**: Without it, overlapping agents would stack invisibly. Jitter lets users see agent count and individual dots. Deterministic offsets prevent visual flickering.

### 4. Graph topology loading: Regenerate world from config + seed

Add `load_graph_topology(episode_dir)` to `data.py`. It reads `config.json` to extract `WorldConfig` and `seed`, calls `generate_world(config, seed)`, and returns the node dict with adjacency lists. Cached with `@st.cache_data`.

**Why regenerate**: The SQLite database stores agent snapshots but not node topology. Since world generation is deterministic, regenerating from config + seed is reliable and requires no schema changes.

**Alternative considered**: Storing node topology as a separate JSON file in episode output. This would be simpler but requires changes to the simulation runner — a larger blast radius for a viz-only feature.

### 5. Tick control: Single tick slider (not range)

Use a single-value `st.slider` for tick selection rather than the existing `tick_range_selector` (which returns a range). The spatial view shows a snapshot at a single point in time.

**Why single slider**: The spatial graph shows the state at one moment. A range selector doesn't make sense for a spatial snapshot — you want to scrub to a specific tick, not select a window.

### 6. Node stats from agent_snapshots aggregation

Compute per-node stats (agent count, total wealth at node, etc.) by filtering `agent_snapshots` for the selected tick and grouping by location. The static node properties (type, resource distribution, NPC config) come from the regenerated world.

**Why aggregate from snapshots**: The agent_snapshots table already has location and credits per tick. No need for a separate node-level stats table.

## Risks / Trade-offs

- **[Large episodes slow down]** → Loading all agent_snapshots into memory for a 500-tick × 20-agent episode is ~10K rows, which is fine. For much larger episodes, the `@st.cache_data` decorator ensures queries run once.
- **[Spring layout non-deterministic across runs]** → Pass a fixed `seed` parameter to `spring_layout()` for reproducible positioning.
- **[Agent jitter obscures small node]** → Cap jitter radius relative to the minimum edge length in the layout. Keep jitter small enough that agents remain visually "at" their node.
- **[Config.json missing seed]** → Validate that config contains a seed field. Show an error message in the panel if topology can't be reconstructed.
