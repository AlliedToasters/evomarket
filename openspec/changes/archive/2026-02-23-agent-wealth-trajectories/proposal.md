## Why

The dashboard currently shows only macro-level time series (aggregate credit supply, Gini, population). There is no way to inspect individual agent performance — how each agent's wealth evolves over its lifetime, which agent types tend to accumulate or lose credits, or how long agents survive. An agent-focused panel would let users drill into micro-level dynamics and compare strategies.

## What Changes

- Add a new visualization panel ("Agent Wealth Trajectories") with two sections:
  - **Wealth trajectory chart**: Per-agent credit balance lines over each agent's lifetime, colored by agent type using the existing `AGENT_TYPE_COLORS` palette.
  - **Agent summary table**: Sortable table showing each agent's net worth, lifetime, agent type, and key stats derived from `result.json` agent summaries.
- Add a data-layer helper to load agent summaries from `result.json` as a DataFrame.
- Register the panel in `app.py`.

## Capabilities

### New Capabilities
- `viz-agent-trajectories`: Panel rendering agent credit balance lines over time colored by type, plus a sortable agent summary table.

### Modified Capabilities
- `viz-data-layer`: Add a function to load agent summaries from `result.json` as a DataFrame with columns for net worth, lifetime, agent type, etc.

## Impact

- New file: `visualization/panels/agent_trajectories.py`
- Modified file: `visualization/data.py` (new query function)
- Modified file: `visualization/app.py` (panel import)
- No new dependencies — uses existing Altair, Pandas, Streamlit stack.
