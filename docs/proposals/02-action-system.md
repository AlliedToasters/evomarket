# Proposal: Action System

## Change ID
`action-system`

## Summary
Define all agent action types, their validation rules, and their resolution logic. This is the vocabulary of what agents can do each tick and how conflicts are resolved during simultaneous execution.

## Motivation
The action system is the interface between agent decision-making and the world simulation. Clean action definitions with strict validation ensure that the tick engine can process actions without edge-case surprises, and that invalid actions degrade gracefully to idle.

## What's Changing

### New Files
- `evomarket/engine/actions.py` — Action types, validation, resolution
- `tests/test_actions.py`

### Action Types (as Pydantic models, all inheriting from BaseAction)

```
MoveAction(target_node: str)
HarvestAction()
PostOrderAction(side: BuySell, commodity: CommodityType, quantity: int, price: float)
AcceptOrderAction(order_id: str)
ProposeTradeAction(target_agent: str, offer: TradeOffer, request: TradeRequest)
AcceptTradeAction(trade_id: str)
SendMessageAction(target: str | Literal["all"], text: str)
UpdateWillAction(distribution: dict[str, float])
InspectAction(target_agent: str)
IdleAction()
```

**TradeOffer / TradeRequest:** `dict[CommodityType | Literal["credits"], int | float]` — what you're giving / what you want.

### AgentTurnResult
Each agent's turn produces:
- `action: BaseAction` — the chosen action
- `prompt_edit: str | None` — optional scratchpad update (free action)

### Validation Rules (per action type)

| Action | Validation |
|---|---|
| Move | Target must be adjacent to current node |
| Harvest | Current node must be a RESOURCE node with stockpile > 0 |
| PostOrder | Agent must have sufficient credits (buy) or inventory (sell). Under max_open_orders limit |
| AcceptOrder | Order must exist, be at agent's node, and agent must have funds/inventory to fill it |
| ProposeTrade | Target must be at same node, agent must have offered items, under max_pending_trades |
| AcceptTrade | Trade must be pending for this agent, both parties must still have required items |
| SendMessage | Target must be at same node (or "all" for broadcast at current node) |
| UpdateWill | Percentages must be ≥ 0, beneficiary IDs must be valid agent IDs |
| Inspect | Target must be at same node and alive |
| Idle | Always valid |

**Invalid actions become IdleAction with a warning log.**

### Resolution Logic

`resolve_actions(world: WorldState, actions: dict[str, BaseAction]) -> list[ActionResult]`

- Assigns random priority ordering to all agents for this tick (using world RNG)
- Resolves actions in priority order for conflict-sensitive actions (harvest, accept_order)
- Non-conflicting actions (move, message, will update, inspect) resolve independently
- Returns a list of ActionResult objects describing what happened

**ActionResult:**
- `agent_id: str`
- `action: BaseAction`
- `success: bool`
- `details: str` (human-readable description of what happened)
- `state_mutations: list[StateMutation]` (optional, for logging)

### Conflict Resolution
- **Harvest conflict:** Multiple agents harvest same node with insufficient stock → priority order, first N get resources, rest get nothing (action still consumed)
- **AcceptOrder conflict:** Multiple agents accept same order → highest priority agent wins, others' actions fail
- **AcceptTrade conflict:** Trade proposals are directed, so no conflict possible

## Acceptance Criteria
- All action types validate correctly (valid actions pass, invalid actions caught)
- Invalid actions convert to IdleAction with warning
- Conflict resolution is deterministic given RNG seed
- Resolution preserves the fixed-supply invariant
- Actions that fail due to conflict are logged with clear reasons
- Full test coverage including edge cases: zero-balance trades, self-trades, trades with dead agents

## Dependencies
- `core-data-models` (requires world, agent, commodity types)

## Estimated Complexity
Medium-high. ~400-600 lines of action code, ~500-700 lines of tests (many edge cases).
