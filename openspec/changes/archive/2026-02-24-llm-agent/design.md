## Context

Phase 0 is complete: the tick engine, heuristic agents, and viz dashboard are validated. The existing `BaseAgent` interface (`decide(AgentObservation) -> AgentTurnResult`) cleanly separates agent logic from engine execution. The simulation runner already handles agent instantiation via `AgentFactory`, wraps `decide()` in try/except with idle fallback, and tracks per-agent metadata.

LLM agents introduce a fundamentally different performance profile — seconds per tick instead of microseconds — but the interface contract is identical. The design adds three internal layers (prompt renderer, LLM backend, action parser) that compose inside a single `LLMAgent.decide()` call.

## Goals / Non-Goals

**Goals:**
- Prove an LLM can play the game through the existing BaseAgent interface
- Support any OpenAI-compatible inference endpoint (Ollama, vLLM, LM Studio, OpenRouter) via a single backend class
- Keep prompts token-efficient for small models (4k-8k context windows)
- Parse LLM responses fault-tolerantly — extract intent, don't enforce syntax
- Provide a persistent scratchpad so agents can maintain state across ticks
- Enable side-by-side comparison of LLM vs heuristic agents using existing viz dashboard
- Add CLI flags for LLM mode without modifying core engine or simulation logic

**Non-Goals:**
- Evolution or genetic optimization of agents (Phase 2)
- Fine-tuning or LoRA adapters (Phase 2)
- Multi-turn conversation or chain-of-thought prompting strategies
- Parallel/async LLM calls across agents (future optimization)
- Custom tokenizer integration for precise token counting

## Decisions

### D1: Three-layer architecture inside LLMAgent

`LLMAgent.decide()` composes three pure-ish functions: `render_prompt(observation, scratchpad) -> str`, `backend.generate(prompt) -> str`, `parse_response(text) -> (Action, scratchpad_update)`.

**Why:** Each layer is independently testable and replaceable. The prompt renderer and action parser are pure functions with no I/O. The backend is the only layer with network access. This makes it trivial to test prompt rendering and action parsing without an LLM, and to swap inference providers without touching prompt or parsing logic.

**Alternatives considered:**
- Single monolithic decide() — rejected for testability
- LangChain/structured output library — rejected for dependency weight and loss of control over fault-tolerant parsing

### D2: Single LLMBackend class targeting OpenAI chat completions format

One concrete class with `__init__(base_url, model, api_key, temperature, max_tokens)` and `generate(prompt) -> str`. Uses `requests` directly against the `/v1/chat/completions` endpoint. No abstract base class, no provider-specific subclasses.

**Why:** Ollama, vLLM, LM Studio, and OpenRouter all expose the same OpenAI-compatible API. The only differences are `base_url` and `api_key`. A single class with constructor parameters covers all providers. Adding an abstract hierarchy would be premature abstraction with zero current benefit.

**Alternatives considered:**
- Abstract LLMBackend with OllamaBackend, VLLMBackend subclasses — rejected; identical API surface means no behavioral differences to specialize
- `openai` Python SDK — rejected to avoid adding a dependency; raw `requests` to `/v1/chat/completions` is ~15 lines

### D3: Structured response format with generous parsing

The prompt asks the LLM to respond with:
```
ACTION: <action_string>
SCRATCHPAD: <optional notes>
REASONING: <optional explanation>
```

The parser extracts ACTION and SCRATCHPAD sections. REASONING is logged but not used. Parsing strategy: try exact structured match first, then regex fallback with case-insensitive matching, then default to `IdleAction`.

**Why:** Small models (7B-8B) are unreliable with JSON output. A line-oriented format is more robust. Generous parsing (handle extra whitespace, wrong casing, partial node name matches, minor typos) maximizes the chance of extracting a valid action from imperfect LLM output.

**Alternatives considered:**
- JSON output format — rejected; small models frequently produce malformed JSON
- Tool-calling / function-calling API — rejected; not supported by all providers, adds complexity

### D4: Token-efficient prompt as compressed reference card

The preamble is a compressed reference card (~200-300 tokens), NOT a verbose tutorial. Uses abbreviated syntax, compact tables, and terse descriptions. World state is rendered as a structured character sheet. The live scratchpad token count is included in the preamble so the agent can self-manage context.

**Why:** Target models have 4k-8k context windows. Every wasted token in the preamble is a token the agent can't use for world state or scratchpad. The preamble is repeated every tick — inefficiency compounds.

**Alternatives considered:**
- Verbose tutorial-style preamble — rejected for token waste
- System message vs user message split — deferred; start with single user message, optimize later

### D5: LLMAgentFactory wired through CLI flags

The CLI gets `--agent-type {heuristic,llm}` (default: heuristic), `--model` (default: qwen3:8b), `--llm-url` (default: http://localhost:11434/v1), and `--llm-api-key` (default: empty). When `--agent-type llm`, the runner creates an `LLMAgentFactory` instead of `HeuristicAgentFactory`. The factory creates `LLMAgent` instances sharing a single `LLMBackend`.

**Why:** Minimal CLI surface. The factory pattern is already established. Sharing a single backend instance avoids redundant connection setup and makes it easy to add rate limiting later.

### D6: No TPS target in LLM mode, per-tick wall time logging

When running LLM agents, the runner logs per-tick wall time instead of aggregate TPS. This surfaces per-tick inference cost directly.

**Why:** LLM inference is 100-1000x slower than heuristic agents. A TPS metric would be misleading. Per-tick wall time reveals whether the model is too slow, whether batching would help, and how cost scales with population.

### D7: Action string format and parsing rules

Action strings use a simple format: `action_type arg1 arg2 ...` Examples:
- `move node_iron_peak`
- `harvest`
- `post_order sell iron 3 4500`
- `accept_order ord_001`
- `propose_trade agent_005 offer:iron=2 request:credits=5000`
- `idle`

The parser applies fuzzy matching: case-insensitive action type lookup, closest-match node name resolution (Levenshtein or prefix matching), commodity name normalization, and whitespace tolerance.

**Why:** This is the simplest format that covers all action types. Small models handle space-separated tokens better than nested structures. Fuzzy matching reflects the design goal of extracting intent, not enforcing syntax.

## Risks / Trade-offs

- **[Small models produce nonsense actions]** → Every unparseable response becomes IdleAction. Parse failure rate is logged per-agent for monitoring. If >50% of actions are idle due to parse failures, the prompt or model needs tuning — but the simulation never crashes.
- **[Scratchpad grows unbounded]** → The prompt renderer includes the current scratchpad token count. Future work can add truncation. For Phase 1A with 50-tick episodes, this is not a concern.
- **[Network failures to inference server]** → `LLMBackend.generate()` catches request exceptions and returns an empty string. The action parser treats empty strings as IdleAction. Failures are logged with the exception.
- **[LLM agents much slower than heuristic]** → Expected and accepted. 5 agents × 50 ticks at ~1s/inference = ~4 minutes. Acceptable for Phase 1A validation.
- **[Token counting is approximate]** → Using `len(text) // 4` as a rough token estimate. Good enough for scratchpad size display. Not used for any critical logic.
