## ADDED Requirements

### Requirement: CLI entry point
The system SHALL provide a CLI entry point via `python -m evomarket` that dispatches to subcommands.

#### Scenario: Module invocation
- **WHEN** `python -m evomarket` is run with no arguments
- **THEN** a help message is displayed listing available subcommands

### Requirement: Run subcommand
The `run` subcommand SHALL execute a single episode and save results. It SHALL accept `--config` (path to JSON config file), `--seed` (integer override), `--output-dir` (results directory), `--fast` (disable logging and checkpoints), `--ticks` (override ticks_per_episode), `--agent-type` (heuristic or llm, default: heuristic), `--model` (LLM model name, default: qwen3:8b), `--llm-url` (LLM API base URL, default: http://localhost:11434/v1), `--llm-api-key` (API key for remote providers, default: empty), `--population` (override population_size), and `--max-idle-ticks` (early stop after N ticks with no productive actions, default: 0/disabled).

#### Scenario: Run with defaults
- **WHEN** `python -m evomarket run` is executed
- **THEN** an episode runs with default `SimulationConfig` using heuristic agents and results are saved to `results/`

#### Scenario: Run with custom config
- **WHEN** `python -m evomarket run --config my_config.json --seed 123` is executed
- **THEN** the config is loaded from the JSON file, seed is overridden to 123, and the episode runs

#### Scenario: Fast mode
- **WHEN** `python -m evomarket run --fast` is executed
- **THEN** the episode runs with logging disabled and no checkpoints written

#### Scenario: LLM agent mode with local Ollama
- **WHEN** `python -m evomarket run --agent-type llm --model qwen3:8b --population 5 --ticks 50` is executed
- **THEN** an episode runs with 5 LLM agents using the Ollama endpoint at localhost:11434

#### Scenario: LLM agent mode with remote provider
- **WHEN** `python -m evomarket run --agent-type llm --model anthropic/claude-sonnet-4 --llm-url https://openrouter.ai/api/v1 --llm-api-key sk-...` is executed
- **THEN** an episode runs using the specified remote LLM endpoint with authentication

#### Scenario: LLM mode logs per-tick wall time
- **WHEN** an episode runs with `--agent-type llm`
- **THEN** each tick's wall time is logged to stdout

#### Scenario: Population override
- **WHEN** `python -m evomarket run --population 5` is executed
- **THEN** the simulation runs with 5 agents regardless of the default population_size

#### Scenario: Idle streak early stop
- **WHEN** `python -m evomarket run --max-idle-ticks 10` is executed and no productive actions occur for 10 consecutive ticks
- **THEN** the simulation stops early and saves partial results

### Requirement: Analyze subcommand
The `analyze` subcommand SHALL load a completed episode's SQLite database and print summary statistics.

#### Scenario: Analyze episode
- **WHEN** `python -m evomarket analyze results/episode.sqlite` is executed
- **THEN** summary statistics (total ticks, survivors, trades, Gini, etc.) are printed to stdout

### Requirement: Resume subcommand
The `resume` subcommand SHALL load a checkpoint file and continue the episode from the checkpointed tick. It SHALL accept `--config` (path to JSON config file), `--output-dir` (results directory), `--agent-type` (heuristic or llm, default: heuristic), `--model` (LLM model name), `--llm-url` (LLM API base URL), and `--llm-api-key` (API key for remote providers).

#### Scenario: Resume from checkpoint
- **WHEN** `python -m evomarket resume checkpoint_tick_250.json` is executed
- **THEN** the episode resumes from tick 251 and runs to completion

#### Scenario: Resume with LLM agents
- **WHEN** `python -m evomarket resume checkpoint.json --agent-type llm --model qwen3:8b` is executed
- **THEN** the episode resumes using LLM agents with the specified model and backend

### Requirement: Output directory structure
The `run` subcommand SHALL create an output directory containing: `config.json` (the config used), `episode.sqlite` (event log), `checkpoints/` (checkpoint files), and `result.json` (final EpisodeResult summary).

#### Scenario: Output files created
- **WHEN** an episode completes via `python -m evomarket run --output-dir results/ep_001`
- **THEN** `results/ep_001/` contains `config.json`, `episode.sqlite`, and `result.json`
