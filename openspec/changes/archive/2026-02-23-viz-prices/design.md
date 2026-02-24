## Context

NPC prices are supply-responsive: `price = base_price * (capacity - stockpile) // capacity`. Each node has NPC stockpiles, budgets, and base prices that change every tick as agents sell commodities and stockpiles decay. This state is tracked in `WorldState.nodes[*].npc_*` fields at runtime but is never persisted to the episode database — only aggregate `total_npc_sales` and individual NPC trade records are logged.

The visualization dashboard (`visualization/app.py`) uses a panel registration pattern. Panels are Streamlit render functions receiving `episode_dir` as their sole argument. Data access goes through `visualization/data.py` (cached queries).

## Goals / Non-Goals

**Goals:**
- Persist per-node NPC economic state each tick so it can be visualized post-hoc
- Provide an interactive heatmap panel showing price dynamics across nodes and time
- Allow drilling into a single node's price curve over time

**Non-Goals:**
- Real-time / live-simulation visualization (this is post-hoc episode analysis only)
- Visualizing P2P order-book prices (only NPC prices)
- Adding new NPC pricing logic — purely observational

## Decisions

### 1. New `npc_snapshots` table for per-node-per-tick state

**Choice**: Add a dedicated `npc_snapshots` table with one row per node per tick, storing price, stockpile, and budget.

**Alternatives considered**:
- *Derive prices from trade records*: The `trades` table logs NPC sales, but prices aren't stored — only total credits. Reconstructing stockpile trajectories from trades would be fragile and miss decay effects.
- *Store as JSON in `ticks.metrics_json`*: Would bloat the aggregate metrics table and complicate queries.

**Schema**:
```sql
CREATE TABLE IF NOT EXISTS npc_snapshots (
    tick INTEGER NOT NULL,
    node_id TEXT NOT NULL,
    commodity TEXT NOT NULL,
    price INTEGER NOT NULL,
    stockpile INTEGER NOT NULL,
    budget INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_npc_snapshots_tick ON npc_snapshots(tick);
```

Each row stores: tick, node_id, commodity (e.g. "IRON"), current price (millicredits), current stockpile, and node budget (millicredits). One row per (node, commodity) pair that the node buys.

### 2. Snapshot at end of tick, before flush

**Choice**: Call `log_npc_snapshots(tick, world)` after all actions resolve but before `flush_tick()`. This captures end-of-tick state consistent with agent snapshots.

### 3. Plotly `Heatmap` for the price grid

**Choice**: Use `plotly.graph_objects.Heatmap` with a per-commodity color scale derived from `COMMODITY_COLORS`. Each commodity gets its own heatmap trace in separate tabs.

**Alternatives considered**:
- *Matplotlib/seaborn*: Would work but Plotly integrates natively with Streamlit via `st.plotly_chart` and provides hover tooltips out of the box.
- *Streamlit native heatmap*: Doesn't exist as a built-in widget.

### 4. Node selection via Streamlit selectbox

**Choice**: Use `st.selectbox` for node selection. When a node is selected, show a line chart of price over time for that node (all commodities overlaid).

### 5. Graceful handling of missing table

**Choice**: The panel checks if the `npc_snapshots` table exists before querying. If absent (old episodes), show an informative message instead of crashing.

## Risks / Trade-offs

- **Storage overhead**: One row per (node, commodity) per tick. With 15 nodes averaging ~3 commodities each over 500 ticks ≈ 22,500 rows. Negligible.
- **Old episodes incompatible**: Episodes recorded before this change won't have the `npc_snapshots` table. Mitigation: panel shows a clear "no data" message.
- **Heatmap readability with many nodes**: With 15+ nodes the y-axis gets dense. Mitigation: tick range selector to zoom, and hovering shows exact values.
