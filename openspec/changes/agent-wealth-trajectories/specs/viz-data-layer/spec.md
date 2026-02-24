## ADDED Requirements

### Requirement: Agent summaries query
The system SHALL provide a function `load_agent_summaries(episode_dir: str) -> pd.DataFrame` that loads agent summary data from `result.json` and returns it as a DataFrame.

#### Scenario: Load agent summaries
- **WHEN** `load_agent_summaries(episode_dir)` is called with a directory containing `result.json`
- **THEN** it SHALL return a DataFrame with columns: `agent_id`, `agent_type`, `net_worth`, `lifetime`, `total_trades`, `final_credits`, `cause_of_death`

#### Scenario: Agent type normalization
- **WHEN** `result.json` contains agent_type values like "HarvesterAgent"
- **THEN** the function SHALL normalize them to short names (e.g., "harvester") matching `AGENT_TYPE_COLORS` keys

#### Scenario: Credit conversion
- **WHEN** the function reads credit values from `result.json`
- **THEN** `net_worth` and `final_credits` SHALL be converted from millicredits to display credits (divided by 1000)

#### Scenario: Result is cached
- **WHEN** `load_agent_summaries(episode_dir)` is called multiple times with the same path
- **THEN** it SHALL return cached results via `st.cache_data`

#### Scenario: Missing result file
- **WHEN** `result.json` does not exist at the given path
- **THEN** the function SHALL return an empty DataFrame with the expected columns
