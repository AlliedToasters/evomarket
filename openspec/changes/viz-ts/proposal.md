## Why

The visualization dashboard lacks a time series panel for tracking macro-economic dynamics across ticks. Users need to see how credit distribution, population, inequality, mortality, and trade activity evolve over an episode to understand simulation behavior and identify emergent patterns.

## What Changes

- Add a new "Time Series" panel to the Streamlit dashboard
- Display five sub-charts in a single panel view:
  - **Credit reservoirs** (stacked area): agent credits, NPC budgets, treasury — showing where the fixed credit supply resides over time
  - **Population count** (line): agents alive per tick
  - **Gini coefficient** (line): wealth inequality over time (0–1 scale)
  - **Deaths per tick** (bar): mortality events per tick
  - **Trade volume** (line): total credits traded per tick
- Use existing `visualization/data.py` functions for all data loading
- Register the panel via the existing `app.register_panel()` system

## Capabilities

### New Capabilities
- `viz-time-series`: Time series panel showing macro-economic indicators over simulation ticks

### Modified Capabilities

## Impact

- New file: `visualization/panels/time_series.py`
- Uses existing data functions: `load_tick_metrics()`, `load_agent_snapshots()`
- Uses existing widgets: `tick_range_selector()` from `common.py`
- Uses existing color palettes from `common.py`
- No changes to data layer, app shell, or common utilities
