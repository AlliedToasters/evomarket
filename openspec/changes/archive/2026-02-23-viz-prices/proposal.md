## Why

There is no way to visualize how NPC prices evolve across nodes and time. NPC pricing is supply-responsive (prices drop as stockpiles grow), but this dynamic is invisible to users reviewing episodes. A price heatmap panel would reveal spatial and temporal pricing patterns, making it easy to spot resource scarcity, trade flow effects, and economic imbalances across the world graph.

## What Changes

- Add a new `npc_snapshots` table to the event logging schema to capture per-node NPC state (prices, stockpiles, budgets) each tick
- Add a data-layer query function to load NPC snapshot data from the database
- Build a new visualization panel (`NPC Prices`) with:
  - Heatmap grid: nodes on y-axis, ticks on x-axis, color intensity = price
  - One heatmap per commodity type (tabs or selector)
  - Price curve chart for a selected node showing price over time
- Register the panel in the app shell

## Capabilities

### New Capabilities
- `viz-npc-prices`: NPC price heatmap panel with node selection and price curves

### Modified Capabilities
- `event-logging`: Add `npc_snapshots` table to capture per-node NPC prices, stockpiles, and budgets each tick
- `viz-data-layer`: Add `load_npc_snapshots(db_path)` query function for the new table

## Impact

- **Database schema**: New `npc_snapshots` table added to `logging.py` — existing episodes won't have this data; panel should handle missing table gracefully
- **Simulation loop**: Must call snapshot logging each tick (small perf cost per tick)
- **Visualization**: New panel file under `visualization/panels/`, registered in app shell
- **Dependencies**: Uses existing Streamlit + Plotly stack (no new deps)
