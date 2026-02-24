## Why

The simulation runner produces rich SQLite event logs (6 tables, full per-tick snapshots) but there's no way to visualize or analyze episode results beyond the CLI `analyze` command's text summary. A Streamlit dashboard will let us explore agent behavior, economic dynamics, and spatial patterns interactively. This foundation change creates the shared data layer, app shell, and common widgets so that four visualization panels (time series, agent trajectories, spatial graph, NPC price heatmaps) can be built in parallel worktrees without duplicating query logic or UI scaffolding.

## What Changes

- New `visualization/` package with app shell, centralized data access, and shared UI components
- Streamlit app entry point (`visualization/app.py`) with sidebar navigation and a panel registration pattern — adding a panel is a one-line import
- Centralized SQLite query layer (`visualization/data.py`) backed by `st.cache_data` — panels never query SQLite directly
- Shared color palettes, filter widgets, and layout helpers (`visualization/common.py`)
- Empty `visualization/panels/` package ready for parallel panel development
- The app shell works with zero panels registered (renders a welcome/status page)

## Capabilities

### New Capabilities
- `viz-app-shell`: Streamlit application skeleton with sidebar navigation, panel registration/discovery, and zero-panel welcome page
- `viz-data-layer`: Centralized SQLite query functions and DataFrame construction for all 6 event-log tables (`ticks`, `actions`, `trades`, `deaths`, `messages`, `agent_snapshots`), with `st.cache_data` caching and millicredit→display-credit conversion
- `viz-common`: Shared color palettes (by commodity type, agent type, node type), reusable Streamlit widgets (tick range selector, agent filter, commodity selector), and layout helpers

### Modified Capabilities
<!-- No existing capabilities are modified — this is a new package -->

## Impact

- **New files:** `visualization/app.py`, `visualization/data.py`, `visualization/common.py`, `visualization/__init__.py`, `visualization/panels/__init__.py`
- **Dependencies:** Adds `streamlit`, `plotly`, `networkx`, `pandas` to project dependencies (pyproject.toml)
- **Existing code:** No modifications to any existing modules — reads the SQLite file produced by `evomarket.simulation.logging.EventLogger` as a read-only consumer
- **Data contract:** Queries are designed against the 6-table schema in `logging.py` (`ticks`, `actions`, `trades`, `deaths`, `messages`, `agent_snapshots`) — if that schema changes, `data.py` must be updated
