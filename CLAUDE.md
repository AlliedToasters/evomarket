# EvoMarket

Market simulation engine where autonomous agents trade goods, communicate, and compete in a procedurally-generated economy.

## Project layout

- `evomarket/` — Core source (engine, agents, simulation runner, CLI)
- `tests/` — Test suite (pytest + hypothesis)
- `configs/` — Simulation config JSON files
- `runs/` — Simulation output (gitignored): checkpoints, SQLite logs, result summaries
- `openspec/specs/` — Formal specifications for subsystems
- `visualization/` — Dash-based result visualization panels

## Running simulations

```bash
# Heuristic agents
python -m evomarket run --config configs/config_large.json

# LLM agents (via OpenRouter or any OpenAI-compatible API)
python -m evomarket run --agent-type llm --model anthropic/claude-3.5-haiku \
  --llm-url https://openrouter.ai/api/v1 --llm-api-key $OPENROUTER_API_KEY \
  --config configs/config_trinity16.json --output-dir runs/my_experiment
```

## Key conventions

- Prices are stored internally as millicredits (int); display as credits (float / 1000)
- `.env.local` holds API keys (gitignored)
- CI: ruff lint + ruff format + pytest (all must pass)
