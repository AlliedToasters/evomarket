## 1. Data Layer

- [x] 1.1 Add `load_graph_topology(episode_dir)` to `visualization/data.py` — read `config.json`, extract `world_config` + `seed`, call `generate_world()`, return node metadata dict with adjacency edges. Decorate with `@st.cache_data`.

## 2. Panel Implementation

- [x] 2.1 Create `visualization/panels/spatial_graph.py` with `render_spatial_graph(episode_dir)` function and `register_panel("Spatial Graph", render_spatial_graph)` call at module level
- [x] 2.2 Implement graph layout — build a `networkx.Graph` from topology, compute `spring_layout(seed=42)`, cache the layout with `@st.cache_data`
- [x] 2.3 Implement edge rendering — create a Plotly `Scatter` trace for edges using `None`-separated line segments between adjacent node positions
- [x] 2.4 Implement node rendering — create one `Scatter` trace per `NodeType`, colored by `NODE_TYPE_COLORS`, with node name labels and hover text (name, type, primary resource, NPC buys)
- [x] 2.5 Implement tick slider — add `st.slider` for single tick selection, range from 0 to max tick in `agent_snapshots`
- [x] 2.6 Implement agent rendering — filter `agent_snapshots` for selected tick, position agents at their node with deterministic jitter, size markers by credits, add hover text (agent_id, credits, inventory, age, location)
- [x] 2.7 Assemble the full Plotly figure — combine edge, node, and agent traces, add legend entries for node types, set layout to hide axes, render with `st.plotly_chart(use_container_width=True)`

## 3. Integration

- [x] 3.1 Register the panel in `visualization/app.py` — add `import visualization.panels.spatial_graph` and uncomment the spatial_graph import line
- [x] 3.2 Add unit tests in `tests/test_spatial_graph.py` — test `load_graph_topology` returns correct structure, test layout computation caching, test agent jitter produces distinct positions for co-located agents, test hover text formatting
