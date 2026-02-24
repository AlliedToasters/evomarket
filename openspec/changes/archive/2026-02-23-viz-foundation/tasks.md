## 1. Project Setup

- [x] 1.1 Add streamlit, plotly, networkx, pandas to pyproject.toml dependencies
- [x] 1.2 Create `visualization/__init__.py`, `visualization/panels/__init__.py` package structure

## 2. Data Layer (`visualization/data.py`)

- [x] 2.1 Implement `get_connection(db_path)` with `@st.cache_resource` returning a WAL-mode SQLite connection
- [x] 2.2 Implement `load_tick_metrics(db_path)` — query `ticks` table, unpack `metrics_json`, convert millicredit columns to display credits
- [x] 2.3 Implement `load_agent_snapshots(db_path)` — query `agent_snapshots` table, unpack `inventory_json` into per-commodity columns, convert credits
- [x] 2.4 Implement `load_trades(db_path)` — query `trades` table, convert credits to display credits
- [x] 2.5 Implement `load_deaths(db_path)` — query `deaths` table, unpack `estate_json` into estate_credits and per-commodity columns, convert credits
- [x] 2.6 Implement `load_actions(db_path)` — query `actions` table, return tick/agent_id/action_type/success/detail columns
- [x] 2.7 Implement `load_messages(db_path)` — query `messages` table, return tick/sender_id/recipient/text columns
- [x] 2.8 Implement `load_config(episode_dir)` and `load_result(episode_dir)` — load JSON files from episode directory
- [x] 2.9 Implement `load_agent_types(episode_dir)` — extract agent_id→agent_type mapping from result.json agent_summaries
- [x] 2.10 Ensure all DataFrame-returning functions are decorated with `@st.cache_data`

## 3. Common Utilities (`visualization/common.py`)

- [x] 3.1 Define `COMMODITY_COLORS` dict mapping IRON/WOOD/STONE/HERBS to distinct hex colors
- [x] 3.2 Define `AGENT_TYPE_COLORS` dict mapping harvester/trader/social/hoarder/explorer/random to distinct hex colors
- [x] 3.3 Define `NODE_TYPE_COLORS` dict mapping RESOURCE/TRADE_HUB/SPAWN to distinct hex colors
- [x] 3.4 Implement `tick_range_selector(max_tick, key)` — Streamlit range slider returning (start, end) tuple
- [x] 3.5 Implement `agent_filter(agent_ids, key)` — Streamlit multiselect returning selected agents or all if empty
- [x] 3.6 Implement `commodity_selector(key)` — Streamlit multiselect returning selected commodities or all if empty
- [x] 3.7 Implement `format_credits(mc_value)` — millicredit int to formatted display credit string

## 4. App Shell (`visualization/app.py`)

- [x] 4.1 Implement panel registry: `_PANELS` dict and `register_panel(name, render_func)` function
- [x] 4.2 Implement sidebar with episode directory input and validation (checks for `episode.sqlite`)
- [x] 4.3 Implement sidebar panel navigation via radio buttons from registered panels
- [x] 4.4 Implement welcome page shown when no panels are registered (display episode summary from result.json if available)
- [x] 4.5 Implement main routing: call selected panel's render function with db_path argument

## 5. Testing

- [x] 5.1 Verify app launches with `streamlit run visualization/app.py` and renders welcome page without errors
- [x] 5.2 Verify data layer functions return correct DataFrames against a real episode.sqlite from a test simulation run
