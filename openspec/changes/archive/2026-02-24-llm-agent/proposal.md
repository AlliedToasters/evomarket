## Why

Phase 0 is complete — the game engine, heuristic agents, and visualization dashboard all work. The next milestone is Phase 1A: proving that an LLM can play the game by making decisions each tick through the existing `BaseAgent` interface. No evolution, no OpenClaw — just "can an LLM play the game?"

## What Changes

- Add `LLMAgent` implementing `BaseAgent` — receives observations, renders them to a text prompt, calls an LLM, parses the response into a `BaseAction`
- Add a prompt renderer that converts `AgentObservation` → compact text prompt with three sections: immutable preamble (compressed game rules + action reference), agent scratchpad (mutable, persistent across ticks, with live token count in preamble), and world state (current tick observation)
- Add an action parser that extracts `BaseAction` from freeform LLM text — structured parsing first, regex fallback, then default to `IdleAction`. Also extracts optional scratchpad edits. Logs every parse failure with raw LLM response
- Add an LLM backend class targeting any OpenAI-compatible chat completions API (single class, no abstract hierarchy). Constructor takes `base_url`, `model`, `api_key`, `temperature`, `max_tokens`. Default `base_url` is `http://localhost:11434/v1` (Ollama). Same class works for Ollama, vLLM, LM Studio, OpenRouter. Uses `requests` directly — no `openai` dependency
- Add `--agent-type llm`, `--model`, `--llm-url`, `--llm-api-key` CLI flags to the runner
- Add LLM-aware runner behavior: no TPS target in LLM mode, per-tick wall time logging for monitoring inference cost
- Add tests for prompt rendering and action parsing

## Capabilities

### New Capabilities
- `llm-agent`: LLMAgent class implementing BaseAgent, orchestrating prompt rendering → LLM call → action parsing per tick
- `prompt-renderer`: Pure function converting AgentObservation to a token-efficient text prompt (preamble + scratchpad + world state)
- `action-parser`: Fault-tolerant extraction of BaseAction and scratchpad edits from freeform LLM text responses
- `llm-backend`: OpenAI-compatible chat completions client (single class covering Ollama, vLLM, LM Studio, OpenRouter)

### Modified Capabilities
- `simulation-cli`: Adding `--agent-type`, `--model`, `--llm-url`, `--llm-api-key` flags to the `run` subcommand

## Impact

- **New files**: `evomarket/agents/llm_agent.py`, `evomarket/agents/prompt_renderer.py`, `evomarket/agents/action_parser.py`, `evomarket/agents/llm_backend.py`, `tests/test_prompt_renderer.py`, `tests/test_action_parser.py`
- **Modified files**: `evomarket/cli.py` (new CLI flags + LLM agent factory wiring), `evomarket/simulation/config.py` (relax `agent_mix` validation for LLM mode)
- **Dependencies**: `requests` (already available in Python ecosystem, no new package needed)
- **No changes** to core engine, tick pipeline, actions, observations, or existing agent implementations
