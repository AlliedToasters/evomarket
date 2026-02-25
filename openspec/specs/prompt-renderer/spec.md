## ADDED Requirements

### Requirement: render_prompt produces complete prompt text
The system SHALL provide a `render_prompt(observation, scratchpad, agent_id)` function in `evomarket/agents/prompt_renderer.py` that returns a string containing three sections: preamble, scratchpad, and world state.

#### Scenario: Prompt contains all three sections
- **WHEN** `render_prompt(observation, scratchpad, agent_id)` is called
- **THEN** the returned string contains a preamble section, a scratchpad section, and a world state section in that order

### Requirement: Preamble is a compressed reference card
The preamble section SHALL contain compressed game rules and an action reference in a compact format optimized for token efficiency. It SHALL NOT be a verbose tutorial. Action filtering uses pre-computed `ActionAvailability` from the observation layer (see `observation.py`), so the renderer formats pre-computed data rather than re-deriving predicates.

#### Scenario: Preamble includes action reference
- **WHEN** a prompt is rendered
- **THEN** the preamble lists valid action types (filtered by `ActionAvailability`) with their argument formats

#### Scenario: Preamble includes core game rules
- **WHEN** a prompt is rendered
- **THEN** the preamble describes survival tax, harvesting, trading, NPC pricing, and death conditions in compressed form

#### Scenario: Preamble is token-efficient
- **WHEN** a prompt is rendered with no scratchpad and minimal world state
- **THEN** the preamble section is under 400 tokens (estimated as `len(text) // 4`)

### Requirement: Preamble includes live scratchpad token count
The preamble SHALL display the current approximate token count of the scratchpad section.

#### Scenario: Scratchpad size shown in preamble
- **WHEN** `render_prompt` is called with a scratchpad of "buy iron at node_mine"
- **THEN** the preamble includes the approximate token count of that scratchpad text

#### Scenario: Empty scratchpad shows zero
- **WHEN** `render_prompt` is called with an empty scratchpad
- **THEN** the preamble shows a scratchpad token count of 0

### Requirement: Scratchpad section displays agent's persistent notes
The scratchpad section SHALL display the agent's current scratchpad content verbatim.

#### Scenario: Non-empty scratchpad rendered
- **WHEN** `render_prompt` is called with scratchpad "Strategy: harvest iron then sell at hub"
- **THEN** the scratchpad section contains that exact text

#### Scenario: Empty scratchpad rendered
- **WHEN** `render_prompt` is called with an empty scratchpad
- **THEN** the scratchpad section is present but empty or contains a placeholder

### Requirement: World state section renders structured observation data
The world state section SHALL render the agent's current state, node information, nearby agents, orders, messages, and trade proposals in a structured character-sheet format.

#### Scenario: Agent state rendered
- **WHEN** `render_prompt` is called with an observation where `agent_state.credits = 15000` and `agent_state.inventory = {IRON: 3}`
- **THEN** the world state section displays the agent's credits and inventory

#### Scenario: Node information rendered
- **WHEN** the observation shows the agent at a RESOURCE node with adjacent nodes
- **THEN** the world state section displays the node ID, type, NPC prices, resource availability, and adjacent node list

#### Scenario: Nearby agents rendered
- **WHEN** the observation includes agents present at the same node
- **THEN** the world state section lists those agents with their IDs

#### Scenario: Orders and proposals rendered
- **WHEN** the observation includes posted orders and pending trade proposals
- **THEN** the world state section displays them in a readable format

#### Scenario: Messages rendered
- **WHEN** the observation includes received messages
- **THEN** the world state section displays sender, text, and tick for each message

### Requirement: Prompt includes response format instructions
The prompt SHALL instruct the LLM to respond with `ACTION:`, `SCRATCHPAD:` (optional), and `REASONING:` (optional) sections.

#### Scenario: Response format shown
- **WHEN** a prompt is rendered
- **THEN** the prompt includes instructions specifying the ACTION/SCRATCHPAD/REASONING response format
