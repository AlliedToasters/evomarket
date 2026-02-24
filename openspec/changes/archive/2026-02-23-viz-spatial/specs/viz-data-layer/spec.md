## ADDED Requirements

### Requirement: Graph topology loading
The system SHALL provide a function `load_graph_topology(episode_dir: str) -> dict` that reconstructs the world graph from the episode's `config.json` file. The returned dict SHALL contain node metadata and adjacency information sufficient to render the spatial graph.

#### Scenario: Load topology from valid episode
- **WHEN** `load_graph_topology(episode_dir)` is called with a directory containing a valid `config.json` with `world_config` and `seed` fields
- **THEN** it SHALL return a dict with keys: `nodes` (dict of node_id → node info including `name`, `node_type`, `adjacent_nodes`, `resource_distribution`, `npc_buys`), and `edges` (list of `[node_a, node_b]` pairs)

#### Scenario: Result is cached
- **WHEN** `load_graph_topology(episode_dir)` is called multiple times with the same directory
- **THEN** it SHALL return cached results via `@st.cache_data`

#### Scenario: Missing seed in config
- **WHEN** `config.json` does not contain a `seed` field
- **THEN** the function SHALL raise a `ValueError` with a descriptive message
