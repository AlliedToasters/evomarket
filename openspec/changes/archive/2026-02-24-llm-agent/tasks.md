## 1. LLM Backend

- [x] 1.1 Create `evomarket/agents/llm_backend.py` with `LLMBackend` class: constructor takes `base_url` (default `http://localhost:11434/v1`), `model` (required), `api_key` (default `""`), `temperature` (default 0.7), `max_tokens` (default 256)
- [x] 1.2 Implement `generate(prompt: str) -> str` — POST to `{base_url}/chat/completions` with OpenAI chat format, extract response text from `choices[0].message.content`
- [x] 1.3 Add error handling: catch `requests.RequestException`, log WARNING with error details, return empty string on failure

## 2. Prompt Renderer

- [x] 2.1 Create `evomarket/agents/prompt_renderer.py` with `render_prompt(observation, scratchpad, agent_id) -> str` function
- [x] 2.2 Implement compressed preamble section: game rules reference card, action format reference (all action types with argument syntax), response format instructions (ACTION/SCRATCHPAD/REASONING), live scratchpad token count
- [x] 2.3 Implement scratchpad section: display agent's current scratchpad content verbatim
- [x] 2.4 Implement world state section: agent state (credits, inventory, location, age), node info (type, NPC prices, resources, adjacent nodes), nearby agents, posted orders, pending proposals, received messages

## 3. Action Parser

- [x] 3.1 Create `evomarket/agents/action_parser.py` with `parse_response(text: str) -> tuple[Action, str | None]` function
- [x] 3.2 Implement structured parsing: extract `ACTION:` line, split into action type + args, construct appropriate Action model. Handle all 10 action types
- [x] 3.3 Implement regex fallback: case-insensitive keyword matching for action types when structured parsing fails
- [x] 3.4 Implement SCRATCHPAD section extraction: extract text after `SCRATCHPAD:` prefix until next section or end of text
- [x] 3.5 Add generous input tolerance: strip whitespace, normalize casing, handle commodity name variations (iron/Iron/IRON)
- [x] 3.6 Add parse failure logging: log WARNING with full raw response text when falling back to IdleAction

## 4. LLM Agent

- [x] 4.1 Create `evomarket/agents/llm_agent.py` with `LLMAgent(BaseAgent)` class: constructor takes `LLMBackend` instance
- [x] 4.2 Implement `on_spawn(agent_id, config)`: store agent_id and config for prompt rendering
- [x] 4.3 Implement `decide(observation) -> AgentTurnResult`: render prompt → call backend → parse response → return result. Catch all exceptions and return IdleAction on failure
- [x] 4.4 Implement scratchpad persistence: maintain internal scratchpad string, update it when parser extracts scratchpad content, include in AgentTurnResult.scratchpad_update
- [x] 4.5 Create `LLMAgentFactory(AgentFactory)`: constructor takes `LLMBackend` and `SimulationConfig`, creates `LLMAgent` instances sharing the backend, calls `on_spawn`

## 5. CLI Integration

- [x] 5.1 Add `--agent-type` flag to run subcommand (choices: heuristic, llm; default: heuristic)
- [x] 5.2 Add `--model` flag (default: qwen3:8b), `--llm-url` flag (default: http://localhost:11434/v1), `--llm-api-key` flag (default: empty string)
- [x] 5.3 Add `--population` flag to override population_size
- [x] 5.4 Wire LLM agent factory: when `--agent-type llm`, create `LLMBackend` and `LLMAgentFactory` instead of `HeuristicAgentFactory`. Build a SimulationConfig with population_size matching `--population` and an LLM-compatible agent_mix
- [x] 5.5 Add per-tick wall time logging for LLM mode: print tick number and elapsed seconds after each tick when agent-type is llm

## 6. Tests

- [x] 6.1 Create `tests/test_prompt_renderer.py`: test all three sections render correctly, test preamble includes scratchpad token count, test token efficiency (preamble under 400 tokens), test with empty and populated observations
- [x] 6.2 Create `tests/test_action_parser.py`: test parsing well-formed actions for all 10 types, test regex fallback for malformed responses, test SCRATCHPAD extraction (single-line, multi-line, absent), test IdleAction for unparseable input, test generous tolerance (whitespace, casing, commodity names)
