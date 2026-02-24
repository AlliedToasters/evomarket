## 1. Panel Module Setup

- [x] 1.1 Create `visualization/panels/__init__.py` (empty) if it doesn't exist
- [x] 1.2 Create `visualization/panels/time_series.py` with the render function skeleton and `register_panel("Time Series", render)` call

## 2. Data Preparation

- [x] 2.1 Implement credit reservoir computation: load agent snapshots, group by tick, sum credits; compute system credits as `total_supply - agent_credits`
- [x] 2.2 Load tick metrics and filter to selected tick range for population, Gini, deaths, and trade volume

## 3. Chart Implementation

- [x] 3.1 Build credit reservoirs stacked area chart (Altair) with agent vs system credit series
- [x] 3.2 Build population count line chart from `agents_alive`
- [x] 3.3 Build Gini coefficient line chart with y-axis fixed to 0–1
- [x] 3.4 Build deaths per tick bar chart from `agents_died`
- [x] 3.5 Build trade volume line chart from `total_trade_volume`

## 4. Integration

- [x] 4.1 Add tick range selector widget using `common.tick_range_selector`
- [x] 4.2 Render all five charts vertically stacked with `use_container_width=True`
- [x] 4.3 Uncomment the `import visualization.panels.time_series` line in `app.py`

## 5. Testing

- [x] 5.1 Add unit tests for credit reservoir computation logic
- [x] 5.2 Verify panel renders without errors on sample episode data
