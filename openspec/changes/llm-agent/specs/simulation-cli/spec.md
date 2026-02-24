## MODIFIED Requirements

### Requirement: Run subcommand
The `run` subcommand SHALL execute a single episode and save results. It SHALL accept `--config` (path to JSON config file), `--seed` (integer override), `--output-dir` (results directory), `--fast` (disable logging and checkpoints), `--ticks` (override ticks_per_episode), `--agent-type` (heuristic or llm, default: heuristic), `--model` (LLM model name, default: qwen3:8b), `--llm-url` (LLM API base URL, default: http://localhost:11434/v1), `--llm-api-key` (API key for remote providers, default: empty), and `--population` (override population_size).

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
