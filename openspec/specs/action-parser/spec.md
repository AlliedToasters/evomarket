## ADDED Requirements

### Requirement: parse_response extracts action and scratchpad
The system SHALL provide a `parse_response(text)` function in `evomarket/agents/action_parser.py` that returns a tuple of `(Action, scratchpad_update: str | None)`.

#### Scenario: Well-formed response parsed
- **WHEN** `parse_response` is called with `"ACTION: harvest\nSCRATCHPAD: remember to sell\nREASONING: need resources"`
- **THEN** it returns `(HarvestAction(), "remember to sell")`

#### Scenario: Action-only response parsed
- **WHEN** `parse_response` is called with `"ACTION: idle"`
- **THEN** it returns `(IdleAction(), None)`

### Requirement: Structured parsing attempted first
The parser SHALL first attempt exact structured parsing — looking for `ACTION:` prefix on a line, extracting the action string, and parsing it into an Action.

#### Scenario: Exact match for move action
- **WHEN** `parse_response` is called with `"ACTION: move node_iron_peak"`
- **THEN** it returns a `MoveAction(target_node="node_iron_peak")`

#### Scenario: Exact match for post_order action
- **WHEN** `parse_response` is called with `"ACTION: post_order sell iron 3 4500"`
- **THEN** it returns a `PostOrderAction(side="sell", commodity=CommodityType.IRON, quantity=3, price=4500)`

### Requirement: Regex fallback for malformed responses
If structured parsing fails, the parser SHALL attempt regex-based extraction of action intent from the full response text.

#### Scenario: Action without prefix
- **WHEN** `parse_response` is called with `"I think I should harvest resources now"`
- **THEN** the regex fallback extracts `HarvestAction()` from the keyword "harvest"

#### Scenario: Mixed case handling
- **WHEN** `parse_response` is called with `"ACTION: MOVE node_iron_peak"`
- **THEN** it returns `MoveAction(target_node="node_iron_peak")` (case-insensitive matching)

### Requirement: Unparseable responses become IdleAction
If both structured parsing and regex fallback fail, the parser SHALL return `IdleAction`.

#### Scenario: Complete gibberish
- **WHEN** `parse_response` is called with `"asdfghjkl 12345"`
- **THEN** it returns `(IdleAction(), None)`

#### Scenario: Empty response
- **WHEN** `parse_response` is called with `""`
- **THEN** it returns `(IdleAction(), None)`

### Requirement: Parse failures logged with raw response
Every parse failure (fallback to IdleAction) SHALL be logged at WARNING level with the full raw LLM response text.

#### Scenario: Gibberish logged
- **WHEN** `parse_response` is called with an unparseable string
- **THEN** a WARNING log entry is emitted containing the raw response text

### Requirement: Generous input tolerance
The parser SHALL handle extra whitespace, wrong casing, minor misspellings of commodity names, and partial matches for node names.

#### Scenario: Extra whitespace tolerated
- **WHEN** `parse_response` is called with `"ACTION:   move   node_iron_peak  "`
- **THEN** it returns `MoveAction(target_node="node_iron_peak")`

#### Scenario: Commodity name normalization
- **WHEN** `parse_response` is called with `"ACTION: post_order sell Iron 2 3000"`
- **THEN** it returns `PostOrderAction` with `commodity=CommodityType.IRON` (case-insensitive)

### Requirement: SCRATCHPAD section extraction
The parser SHALL extract text following a `SCRATCHPAD:` prefix as the scratchpad update. Content continues until the next section prefix or end of text.

#### Scenario: Multi-line scratchpad
- **WHEN** the response contains `"SCRATCHPAD: line one\nline two\nREASONING: because"`
- **THEN** the scratchpad update is `"line one\nline two"`

#### Scenario: No scratchpad section
- **WHEN** the response contains no `SCRATCHPAD:` prefix
- **THEN** the scratchpad update is `None`

### Requirement: Sell/buy shorthand for post_order
The parser SHALL accept `sell` and `buy` as shorthand for `post_order sell` and `post_order buy` respectively.

#### Scenario: Sell shorthand
- **WHEN** `parse_response` is called with `"ACTION: sell IRON 1 5.0"`
- **THEN** it returns `PostOrderAction(side="sell", commodity=CommodityType.IRON, quantity=1, price=5000)`

#### Scenario: Buy shorthand
- **WHEN** `parse_response` is called with `"ACTION: buy WOOD 2 3.5"`
- **THEN** it returns `PostOrderAction(side="buy", commodity=CommodityType.WOOD, quantity=2, price=3500)`

### Requirement: Float price auto-conversion to millicredits
The parser SHALL accept both integer (millicredits) and float (display credits) prices in `post_order`, `sell`, and `buy` actions. Values less than 1000 are interpreted as display credits and multiplied by 1000 to get millicredits; values >= 1000 are treated as millicredits directly.

#### Scenario: Float price converted
- **WHEN** `parse_response` is called with `"ACTION: post_order sell iron 3 4.5"`
- **THEN** it returns `PostOrderAction` with `price=4500` (4.5 × 1000)

#### Scenario: Large integer stays as millicredits
- **WHEN** `parse_response` is called with `"ACTION: post_order sell iron 3 4500"`
- **THEN** it returns `PostOrderAction` with `price=4500` (unchanged)

### Requirement: All action types parseable
The parser SHALL support parsing all action types: `move`, `harvest`, `post_order`, `sell`, `buy`, `accept_order`, `propose_trade`, `accept_trade`, `send_message`, `update_will`, `inspect`, `idle`.

#### Scenario: accept_order parsed
- **WHEN** `parse_response` is called with `"ACTION: accept_order ord_abc123"`
- **THEN** it returns `AcceptOrderAction(order_id="ord_abc123")`

#### Scenario: send_message parsed
- **WHEN** `parse_response` is called with `"ACTION: send_message agent_005 hello there"`
- **THEN** it returns `SendMessageAction(target="agent_005", text="hello there")`

#### Scenario: inspect parsed
- **WHEN** `parse_response` is called with `"ACTION: inspect agent_003"`
- **THEN** it returns `InspectAction(target_agent="agent_003")`
