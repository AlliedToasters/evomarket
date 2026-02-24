## 1. Database Schema & Logging

- [x] 1.1 Add `npc_snapshots` table and index to `_SCHEMA` in `evomarket/simulation/logging.py`
- [x] 1.2 Add `log_npc_snapshots(tick, world)` method to `EventLogger` that buffers one row per (node, commodity) for each commodity the node buys
- [x] 1.3 Add `npc_snapshots` INSERT SQL to `_INSERT_SQL` dict in `flush_tick()`
- [x] 1.4 Call `log_npc_snapshots` in the simulation tick loop (after actions resolve, before `flush_tick`)

## 2. Data Layer

- [x] 2.1 Add `has_npc_snapshots(db_path)` function to `visualization/data.py` that checks if the table exists
- [x] 2.2 Add `load_npc_snapshots(db_path)` function to `visualization/data.py` returning a DataFrame with columns: tick, node_id, commodity, price, stockpile, budget (price/budget in display credits), cached via `@st.cache_data`

## 3. NPC Prices Panel

- [x] 3.1 Create `visualization/panels/npc_prices.py` with `render(episode_dir)` function that registers via `register_panel("NPC Prices", render)`
- [x] 3.2 Implement missing-table guard: check `has_npc_snapshots` and show info message if absent
- [x] 3.3 Add tick range selector using `tick_range_selector` from `viz-common`
- [x] 3.4 Build commodity tabs showing one Plotly heatmap per commodity (nodes on y-axis, ticks on x-axis, price as color intensity using `COMMODITY_COLORS`)
- [x] 3.5 Add node selectbox and price curve line chart (price vs tick, one line per commodity, colored by `COMMODITY_COLORS`)
- [x] 3.6 Add hover tooltips showing node name, tick, and price in display credits

## 4. Integration & Wiring

- [x] 4.1 Uncomment/add `import visualization.panels.npc_prices` in `visualization/app.py` panel imports section

## 5. Tests

- [x] 5.1 Test `log_npc_snapshots` writes correct rows to the database
- [x] 5.2 Test `has_npc_snapshots` returns True/False correctly
- [x] 5.3 Test `load_npc_snapshots` returns correct DataFrame with millicredit conversion
- [x] 5.4 Test panel renders without errors given valid NPC snapshot data
- [x] 5.5 Test panel shows info message when `npc_snapshots` table is missing
