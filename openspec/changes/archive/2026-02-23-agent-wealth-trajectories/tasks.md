## 1. Data Layer

- [x] 1.1 Add `load_agent_summaries(episode_dir) -> pd.DataFrame` to `visualization/data.py` — loads agent summaries from `result.json`, normalizes agent types, converts millicredits to display credits, cached with `@st.cache_data`, returns empty DataFrame if file missing.

## 2. Panel Implementation

- [x] 2.1 Create `visualization/panels/agent_trajectories.py` with `render(episode_dir: str)` function that builds the wealth trajectory chart and agent summary table.
- [x] 2.2 Implement wealth trajectory chart: join `load_agent_snapshots` with `load_agent_types` on `agent_id`, render Altair multi-line chart with `tick` on x-axis, `credits` on y-axis, color by `agent_type` using `AGENT_TYPE_COLORS`, and `agent_id` as detail channel.
- [x] 2.3 Add tick range slider via `common.tick_range_selector` and agent filter via `common.agent_filter` to filter the trajectory chart data.
- [x] 2.4 Implement agent summary table: load via `load_agent_summaries`, display as `st.dataframe` sorted by `net_worth` descending, with columns: agent_id, agent_type, net_worth, lifetime, total_trades, final_credits, cause_of_death.
- [x] 2.5 Handle empty data cases — show `st.warning` when snapshots or summaries are unavailable.

## 3. Registration

- [x] 3.1 Add `register_panel("Agent Wealth Trajectories", render)` call at module level in `agent_trajectories.py`.
- [x] 3.2 Uncomment or add `import visualization.panels.agent_trajectories` in `visualization/app.py`.

## 4. Testing

- [x] 4.1 Add tests for `load_agent_summaries` — verify column names, type normalization, credit conversion, and empty-file handling.
- [x] 4.2 Add tests for the panel render function — verify it runs without error given valid and empty data.
