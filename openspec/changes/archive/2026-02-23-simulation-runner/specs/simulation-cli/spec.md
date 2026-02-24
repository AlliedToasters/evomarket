## ADDED Requirements

### Requirement: CLI entry point
The system SHALL provide a CLI entry point via `python -m evomarket` that dispatches to subcommands.

#### Scenario: Module invocation
- **WHEN** `python -m evomarket` is run with no arguments
- **THEN** a help message is displayed listing available subcommands

### Requirement: Run subcommand
The `run` subcommand SHALL execute a single episode and save results. It SHALL accept `--config` (path to JSON config file), `--seed` (integer override), `--output-dir` (results directory), and `--fast` (disable logging and checkpoints).

#### Scenario: Run with defaults
- **WHEN** `python -m evomarket run` is executed
- **THEN** an episode runs with default `SimulationConfig` and results are saved to `results/`

#### Scenario: Run with custom config
- **WHEN** `python -m evomarket run --config my_config.json --seed 123` is executed
- **THEN** the config is loaded from the JSON file, seed is overridden to 123, and the episode runs

#### Scenario: Fast mode
- **WHEN** `python -m evomarket run --fast` is executed
- **THEN** the episode runs with logging disabled and no checkpoints written

### Requirement: Analyze subcommand
The `analyze` subcommand SHALL load a completed episode's SQLite database and print summary statistics.

#### Scenario: Analyze episode
- **WHEN** `python -m evomarket analyze results/episode.sqlite` is executed
- **THEN** summary statistics (total ticks, survivors, trades, Gini, etc.) are printed to stdout

### Requirement: Resume subcommand
The `resume` subcommand SHALL load a checkpoint file and continue the episode from the checkpointed tick.

#### Scenario: Resume from checkpoint
- **WHEN** `python -m evomarket resume checkpoint_tick_250.json` is executed
- **THEN** the episode resumes from tick 251 and runs to completion

### Requirement: Output directory structure
The `run` subcommand SHALL create an output directory containing: `config.json` (the config used), `episode.sqlite` (event log), `checkpoints/` (checkpoint files), and `result.json` (final EpisodeResult summary).

#### Scenario: Output files created
- **WHEN** an episode completes via `python -m evomarket run --output-dir results/ep_001`
- **THEN** `results/ep_001/` contains `config.json`, `episode.sqlite`, and `result.json`
