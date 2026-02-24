## Context

The dashboard has a working app shell (`app.py`), data layer (`data.py`), and shared utilities (`common.py`), but no panels yet. The `panels/` directory is empty. The `load_tick_metrics()` function already provides most needed columns: `agents_alive`, `agent_credit_gini`, `agents_died`, `total_trade_volume`. Credit reservoir breakdown (agent vs NPC vs treasury) is not yet available from `load_tick_metrics()` but can be derived from `load_agent_snapshots()` (sum of agent credits per tick) combined with the fixed total supply from `load_config()`.

## Goals / Non-Goals

**Goals:**
- Provide a single-panel time series view with five vertically stacked sub-charts
- Use Altair for charts (Streamlit's native charting library) for consistent look
- Integrate with existing `tick_range_selector` widget for time filtering
- Follow the `register_panel` pattern established in `app.py`

**Non-Goals:**
- Real-time streaming or auto-refresh
- Per-agent time series (that's a separate panel)
- Export/download functionality
- Custom chart themes or interactive tooltips beyond Altair defaults

## Decisions

### 1. Charting library: Altair via `st.altair_chart`
Altair is Streamlit's native grammar-of-graphics library. It supports stacked area charts, shared x-axis encoding, and layered compositions. No additional dependency needed.

**Alternatives considered:** Plotly (heavier, not needed for static time series), matplotlib (less interactive, requires `st.pyplot`).

### 2. Credit reservoir computation from agent snapshots
The stacked area chart needs three series: agent credits (sum), NPC/node budgets, and treasury. `load_tick_metrics()` provides `total_credits_in_circulation` but not the breakdown. We'll compute agent credit totals by grouping `load_agent_snapshots()` by tick and summing `credits`. The NPC+treasury remainder is `total_supply - agent_credits` per tick, using the fixed total supply from `load_config()`.

**Alternatives considered:** Adding new columns to `load_tick_metrics()` — rejected because it would modify the data layer spec and the underlying SQL/metrics collection. The snapshot-based approach works with existing data.

### 3. Layout: five sub-charts stacked vertically
Each sub-chart gets its own `st.altair_chart` call with `use_container_width=True`. This is simpler than Altair `vconcat` (which has sizing issues in Streamlit) and allows Streamlit to handle responsive layout.

### 4. Single file: `visualization/panels/time_series.py`
One module, one `render` function, one `register_panel` call. Keeps the panel self-contained.

## Risks / Trade-offs

- [Large snapshots dataset] → For episodes with many agents and ticks, `load_agent_snapshots()` could be large. Mitigation: data is cached by `@st.cache_data`, and the groupby aggregation is cheap on DataFrames.
- [Two-series reservoir approximation] → We split credits into "agent" vs "system" (NPC + treasury) rather than three separate reservoirs. Mitigation: the tick metrics don't expose NPC vs treasury separately, so this is the best decomposition available without data layer changes.
