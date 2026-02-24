## Context

The dashboard has a Time Series panel showing macro indicators. The `agent_snapshots` table already stores per-agent-per-tick credits, and `result.json` contains `agent_summaries` with net worth, lifetime, and type. The data layer provides `load_agent_snapshots()` and `load_agent_types()`. No per-agent visualization exists yet.

## Goals / Non-Goals

**Goals:**
- Show individual agent credit balance trajectories over time, colored by agent type.
- Provide a sortable summary table with net worth, lifetime, type, and trade count.
- Follow existing panel patterns (Altair charts, `common` widgets, `data` module).
- Support tick range filtering and agent filtering.

**Non-Goals:**
- Inventory or commodity-level trajectories (future panel).
- Agent comparison or diff views.
- Real-time / streaming data support.

## Decisions

1. **Chart library: Altair** — Consistent with the existing Time Series panel. Altair handles multi-line charts with color encoding naturally via `agent_id` detail and `agent_type` color.

2. **One line per agent, colored by type** — Each agent gets its own line in the chart. Lines are colored using `AGENT_TYPE_COLORS` from `common.py`. Agent ID is encoded as a `detail` channel so Altair draws separate lines without adding them to the legend (which would be too crowded with 20+ agents).

3. **Agent summary data from `result.json`** — Add `load_agent_summaries(episode_dir) -> pd.DataFrame` to `data.py`. This returns a DataFrame with columns: `agent_id`, `agent_type`, `net_worth`, `lifetime`, `total_trades`, `final_credits`, `cause_of_death`. The table is rendered via `st.dataframe` with column sorting enabled.

4. **Panel structure** — Two sections stacked vertically:
   - Wealth trajectories chart (Altair multi-line) with tick range slider and optional agent filter.
   - Agent summary table (`st.dataframe`) with default sort by net worth descending.

5. **Data join strategy** — Join `load_agent_snapshots()` with `load_agent_types()` on `agent_id` to get the `agent_type` column for coloring. This avoids duplicating type resolution logic.

## Risks / Trade-offs

- **Many agents = visual clutter**: With 20+ agents the chart may be dense. Mitigated by agent filter widget and Altair's interactive tooltip on hover.
- **Large episodes = slow rendering**: `agent_snapshots` can be large (agents x ticks rows). The existing `st.cache_data` on `load_agent_snapshots` handles repeat renders; Altair's 5000-row default limit may need `alt.data_transformers.disable_max_rows()` — already standard practice in this codebase.
