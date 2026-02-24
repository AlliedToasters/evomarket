## ADDED Requirements

### Requirement: BaseAction model
All action types SHALL inherit from a `BaseAction` Pydantic model. BaseAction SHALL have an `action_type` field that acts as a Literal discriminator for the union type.

#### Scenario: BaseAction has discriminator field
- **WHEN** any action model is instantiated
- **THEN** it SHALL have an `action_type` field matching its specific type string

### Requirement: MoveAction
`MoveAction` SHALL have a `target_node: str` field specifying the destination node ID.

#### Scenario: MoveAction construction
- **WHEN** a MoveAction is created with `target_node="node_iron_peak"`
- **THEN** `action_type` SHALL be `"move"` and `target_node` SHALL be `"node_iron_peak"`

### Requirement: HarvestAction
`HarvestAction` SHALL represent an agent gathering resources at their current node. It has no additional fields beyond `action_type`.

#### Scenario: HarvestAction construction
- **WHEN** a HarvestAction is created
- **THEN** `action_type` SHALL be `"harvest"`

### Requirement: PostOrderAction
`PostOrderAction` SHALL have fields: `side: Literal["buy", "sell"]`, `commodity: CommodityType`, `quantity: int` (positive), `price: int` (in millicredits, positive).

#### Scenario: PostOrderAction construction
- **WHEN** a PostOrderAction is created with side="sell", commodity=IRON, quantity=3, price=5000
- **THEN** all fields SHALL be set and `action_type` SHALL be `"post_order"`

### Requirement: AcceptOrderAction
`AcceptOrderAction` SHALL have an `order_id: str` field identifying which order to fill.

#### Scenario: AcceptOrderAction construction
- **WHEN** an AcceptOrderAction is created with `order_id="order_001"`
- **THEN** `action_type` SHALL be `"accept_order"` and `order_id` SHALL be `"order_001"`

### Requirement: ProposeTradeAction
`ProposeTradeAction` SHALL have fields: `target_agent: str`, `offer: dict[CommodityType | Literal["credits"], int]`, `request: dict[CommodityType | Literal["credits"], int]`.

#### Scenario: ProposeTradeAction construction
- **WHEN** a ProposeTradeAction is created offering 5 IRON and requesting 3000 credits
- **THEN** `offer` SHALL be `{CommodityType.IRON: 5}` and `request` SHALL be `{"credits": 3000}`

### Requirement: AcceptTradeAction
`AcceptTradeAction` SHALL have a `trade_id: str` field identifying which pending trade proposal to accept.

#### Scenario: AcceptTradeAction construction
- **WHEN** an AcceptTradeAction is created with `trade_id="trade_042"`
- **THEN** `action_type` SHALL be `"accept_trade"` and `trade_id` SHALL be `"trade_042"`

### Requirement: SendMessageAction
`SendMessageAction` SHALL have fields: `target: str` (an agent_id or the literal `"all"` for broadcast) and `text: str`.

#### Scenario: SendMessageAction construction for broadcast
- **WHEN** a SendMessageAction is created with target="all" and text="hello"
- **THEN** `action_type` SHALL be `"send_message"`, `target` SHALL be `"all"`, `text` SHALL be `"hello"`

### Requirement: UpdateWillAction
`UpdateWillAction` SHALL have a `distribution: dict[str, float]` field mapping beneficiary agent IDs to percentage shares. Percentages SHALL be non-negative and sum to at most 1.0.

#### Scenario: UpdateWillAction construction
- **WHEN** an UpdateWillAction is created with `distribution={"agent_001": 0.5, "agent_002": 0.5}`
- **THEN** `action_type` SHALL be `"update_will"` and `distribution` SHALL contain both entries

#### Scenario: UpdateWillAction rejects negative percentages
- **WHEN** an UpdateWillAction is created with `distribution={"agent_001": -0.1}`
- **THEN** Pydantic validation SHALL raise a ValidationError

#### Scenario: UpdateWillAction rejects percentages summing over 1.0
- **WHEN** an UpdateWillAction is created with `distribution={"agent_001": 0.6, "agent_002": 0.6}`
- **THEN** Pydantic validation SHALL raise a ValidationError

### Requirement: InspectAction
`InspectAction` SHALL have a `target_agent: str` field identifying which agent to inspect.

#### Scenario: InspectAction construction
- **WHEN** an InspectAction is created with `target_agent="agent_005"`
- **THEN** `action_type` SHALL be `"inspect"` and `target_agent` SHALL be `"agent_005"`

### Requirement: IdleAction
`IdleAction` SHALL represent doing nothing. It has no additional fields beyond `action_type`.

#### Scenario: IdleAction construction
- **WHEN** an IdleAction is created
- **THEN** `action_type` SHALL be `"idle"`

### Requirement: Action discriminated union
An `Action` type alias SHALL be defined as an `Annotated[Union[...], Discriminator("action_type")]` combining all action types. This enables exhaustive matching and automatic Pydantic deserialization.

#### Scenario: Deserialize action from dict
- **WHEN** `{"action_type": "move", "target_node": "node_iron_peak"}` is validated as Action
- **THEN** the result SHALL be a `MoveAction` instance with `target_node="node_iron_peak"`

### Requirement: AgentTurnResult
`AgentTurnResult` SHALL be a Pydantic model with fields: `action: Action` (the chosen action) and `scratchpad_update: str | None` (optional scratchpad text, defaults to None).

#### Scenario: AgentTurnResult with action and scratchpad
- **WHEN** an AgentTurnResult is created with an IdleAction and scratchpad_update="notes"
- **THEN** `action` SHALL be the IdleAction and `scratchpad_update` SHALL be `"notes"`

#### Scenario: AgentTurnResult with action only
- **WHEN** an AgentTurnResult is created with a MoveAction and no scratchpad_update
- **THEN** `scratchpad_update` SHALL be None

### Requirement: ActionResult
`ActionResult` SHALL be a Pydantic model with fields: `agent_id: str`, `action: Action`, `success: bool`, `detail: str` (human-readable description of outcome).

#### Scenario: Successful ActionResult
- **WHEN** an ActionResult is created for a successful harvest
- **THEN** `success` SHALL be True and `detail` SHALL describe what was harvested

#### Scenario: Failed ActionResult
- **WHEN** an ActionResult is created for a failed harvest (no stock)
- **THEN** `success` SHALL be False and `detail` SHALL explain the failure reason
