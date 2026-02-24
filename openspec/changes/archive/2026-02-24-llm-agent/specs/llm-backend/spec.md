## ADDED Requirements

### Requirement: LLMBackend class targeting OpenAI-compatible API
The system SHALL provide an `LLMBackend` class in `evomarket/agents/llm_backend.py` that sends requests to any OpenAI-compatible chat completions endpoint.

#### Scenario: Default construction targets Ollama
- **WHEN** `LLMBackend(model="qwen3:8b")` is constructed with no `base_url`
- **THEN** the backend targets `http://localhost:11434/v1`

#### Scenario: Custom endpoint for vLLM
- **WHEN** `LLMBackend(base_url="http://gpu-server:8000/v1", model="mistral:7b")` is constructed
- **THEN** the backend targets the specified URL

#### Scenario: API key for OpenRouter
- **WHEN** `LLMBackend(base_url="https://openrouter.ai/api/v1", model="anthropic/claude-sonnet-4", api_key="sk-...")` is constructed
- **THEN** the backend sends the API key in the Authorization header

### Requirement: generate method returns LLM text
`LLMBackend.generate(prompt)` SHALL send the prompt as a user message to the chat completions endpoint and return the assistant's response text.

#### Scenario: Successful generation
- **WHEN** `generate("What should I do?")` is called and the server responds with `{"choices": [{"message": {"content": "ACTION: harvest"}}]}`
- **THEN** `"ACTION: harvest"` is returned

### Requirement: Configurable generation parameters
The constructor SHALL accept `temperature` (float, default 0.7), `max_tokens` (int, default 256), and `model` (str, required) parameters that are sent with every request.

#### Scenario: Custom temperature and max_tokens
- **WHEN** `LLMBackend(model="qwen3:8b", temperature=0.3, max_tokens=128)` is constructed
- **THEN** all requests include `temperature=0.3` and `max_tokens=128`

### Requirement: Network error handling
`LLMBackend.generate()` SHALL catch network errors (connection refused, timeout, HTTP errors) and return an empty string. Errors SHALL be logged at WARNING level.

#### Scenario: Connection refused
- **WHEN** `generate(prompt)` is called and the server is unreachable
- **THEN** an empty string is returned
- **AND** a WARNING log entry is emitted with the error details

#### Scenario: HTTP 500 response
- **WHEN** the server returns HTTP 500
- **THEN** an empty string is returned
- **AND** a WARNING log entry is emitted

### Requirement: No openai dependency
The backend SHALL use the `requests` library directly to make HTTP calls. It SHALL NOT depend on the `openai` Python package.

#### Scenario: Import check
- **WHEN** `evomarket/agents/llm_backend.py` is imported
- **THEN** no import of `openai` occurs

### Requirement: Request format follows OpenAI chat completions spec
Requests SHALL be POST to `{base_url}/chat/completions` with JSON body containing `model`, `messages` (array with single user message), `temperature`, and `max_tokens`.

#### Scenario: Request body format
- **WHEN** `generate("hello")` is called with model "qwen3:8b"
- **THEN** the request body is `{"model": "qwen3:8b", "messages": [{"role": "user", "content": "hello"}], "temperature": 0.7, "max_tokens": 256}`
