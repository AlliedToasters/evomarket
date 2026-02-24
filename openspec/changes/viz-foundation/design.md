## Context

EvoMarket simulations produce a `episode.sqlite` database (6 tables: `ticks`, `actions`, `trades`, `deaths`, `messages`, `agent_snapshots`) plus `config.json` and `result.json`. The only analysis tool today is the CLI `analyze` command which prints a text summary. We need an interactive Streamlit dashboard for post-hoc episode analysis. This change builds the shared foundation; four visualization panels will be built in parallel worktrees against it.

**Credit system note:** All credit values in SQLite are stored as millicredits (integers). The data layer must convert to display credits (÷1000) before returning DataFrames to panels.

## Goals / Non-Goals

**Goals:**
- Provide a centralized, cached data access layer that all panels import — no direct SQLite queries from panel code
- Create a Streamlit app shell with sidebar navigation and a panel registration mechanism that makes adding a new panel a one-line import
- Establish shared color palettes and reusable widgets so panels have consistent visual styling
- Design data queries to serve the four planned panels: time series, agent trajectories, spatial graph, NPC price heatmaps

**Non-Goals:**
- Implement any visualization panels (those are separate changes)
- Real-time / live-updating dashboards (this is post-hoc analysis only)
- Multi-episode comparison (single episode at a time)
- Modifying the simulation runner or event logging schema

## Decisions

### 1. Panel registration via a registry dict, not auto-discovery

Panels register by calling a `register_panel(name, module)` function at import time. The app shell imports `visualization.panels` which triggers panel `__init__.py` imports. This is simpler and more explicit than filesystem scanning or decorator magic.

**Alternative considered:** `importlib` + `pkgutil` auto-discovery of panel modules. Rejected because it adds import-order complexity and makes it harder to debug when a panel fails to load.

### 2. Single SQLite connection opened once per session via `st.cache_resource`

The database path is selected via a file picker in the sidebar. Once selected, a `sqlite3.Connection` is cached with `st.cache_resource`. Individual query functions use `st.cache_data` keyed on db_path and relevant parameters.

**Alternative considered:** Opening a new connection per query. Rejected because SQLite in WAL mode supports concurrent reads efficiently and connection setup overhead is unnecessary.

### 3. DataFrames as the universal data exchange format

All `data.py` functions return `pandas.DataFrame`. JSON columns (`metrics_json`, `inventory_json`, `action_json`, `estate_json`, `will_json`) are unpacked into flat DataFrame columns during query. Credit columns are converted from millicredits to display credits.

**Alternative considered:** Returning typed dataclasses or dicts. Rejected because pandas integrates directly with Plotly and Streamlit's `st.dataframe`, and most visualization panels need aggregation/filtering that pandas provides natively.

### 4. Plotly for all charts (not matplotlib/altair)

Plotly provides interactive hover, zoom, and pan natively in Streamlit via `st.plotly_chart`. This is essential for exploring 500-tick time series and spatial graphs.

### 5. Color palettes as plain dicts mapping enum values to hex strings

Commodity colors, agent type colors, and node type colors are defined as module-level dicts in `common.py`. These map string values (matching the SQLite data) to hex color codes.

**Alternative considered:** Plotly color scales. Rejected because we need deterministic, semantically meaningful colors (e.g., IRON always gray, WOOD always brown) across all panels.

### 6. File layout

```
visualization/
├── __init__.py          # empty
├── app.py               # Streamlit entry point, sidebar, panel routing
├── data.py              # all SQLite queries, DataFrame construction, caching
├── common.py            # palettes, widgets, layout helpers
└── panels/
    └── __init__.py      # empty (panels added by other changes)
```

Streamlit is run via `streamlit run visualization/app.py` from the project root, with the episode directory selected in the sidebar.

## Risks / Trade-offs

- **[Large episode files]** → A 500-tick × 20-agent episode produces ~10K snapshot rows. `st.cache_data` keeps the full DataFrame in memory. For the current scale this is fine; if episodes grow to thousands of ticks, query functions could accept tick-range parameters to limit data loaded.
- **[Schema coupling]** → `data.py` queries are tightly coupled to the 6-table SQLite schema in `logging.py`. If the schema changes, `data.py` must be updated. Mitigation: the schema is already stable and covered by tests.
- **[Millicredit conversion]** → If any query forgets to convert millicredits, panels will show inflated numbers. Mitigation: all conversion happens in `data.py` before returning DataFrames — panels never see raw millicredits.
