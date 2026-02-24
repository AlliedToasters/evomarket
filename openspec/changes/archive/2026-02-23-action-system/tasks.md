## 1. Action Type Models

- [x] 1.1 Create `evomarket/engine/actions.py` with BaseAction model and Literal discriminator pattern
- [x] 1.2 Implement all action models: MoveAction, HarvestAction, PostOrderAction, AcceptOrderAction, ProposeTradeAction, AcceptTradeAction, SendMessageAction, UpdateWillAction, InspectAction, IdleAction
- [x] 1.3 Define the `Action` discriminated union type alias
- [x] 1.4 Implement AgentTurnResult and ActionResult models
- [x] 1.5 Add Pydantic validators for UpdateWillAction (non-negative percentages, sum ≤ 1.0) and PostOrderAction (positive quantity/price)

## 2. Action Validation

- [x] 2.1 Implement `validate_action(agent_id, action, world) -> Action` with logging for invalid actions
- [x] 2.2 Implement MoveAction validation (adjacency check)
- [x] 2.3 Implement HarvestAction validation (RESOURCE node type, floor(stockpile) ≥ 1)
- [x] 2.4 Implement PostOrderAction validation (credits/inventory sufficiency, open order limit)
- [x] 2.5 Implement AcceptOrderAction validation (order exists, same node, sufficient funds/inventory)
- [x] 2.6 Implement ProposeTradeAction validation (same node, has offered items, not self-trade, pending trade limit)
- [x] 2.7 Implement AcceptTradeAction validation (trade pending for agent, both parties have items)
- [x] 2.8 Implement SendMessageAction validation (target at same node or "all")
- [x] 2.9 Implement UpdateWillAction validation (beneficiary IDs exist)
- [x] 2.10 Implement InspectAction validation (target alive and at same node)

## 3. Action Resolution

- [x] 3.1 Implement `resolve_actions(world, actions) -> list[ActionResult]` with RNG-based priority ordering
- [x] 3.2 Implement MoveAction resolution (update agent location)
- [x] 3.3 Implement HarvestAction resolution with conflict handling (priority order, commodity selection by highest floor stockpile)
- [x] 3.4 Implement PostOrderAction resolution with escrow (deduct inventory for sell, credits for buy)
- [x] 3.5 Implement AcceptOrderAction resolution with conflict handling (priority wins)
- [x] 3.6 Implement ProposeTradeAction resolution with offer escrow
- [x] 3.7 Implement AcceptTradeAction resolution (execute exchange)
- [x] 3.8 Implement SendMessageAction resolution (enqueue message)
- [x] 3.9 Implement UpdateWillAction resolution (replace agent will)
- [x] 3.10 Implement InspectAction resolution (produce detail string with target state)
- [x] 3.11 Implement NPC sell resolution (supply-responsive pricing from npc_budget)

## 4. Tests

- [x] 4.1 Create `tests/test_actions.py` with test fixtures (small world, agents at various nodes)
- [x] 4.2 Test all action model construction and serialization (discriminated union round-trip)
- [x] 4.3 Test UpdateWillAction Pydantic validators (negative percentages, overflow)
- [x] 4.4 Test validation for each action type: valid cases
- [x] 4.5 Test validation for each action type: invalid cases (wrong node, insufficient resources, etc.)
- [x] 4.6 Test harvest conflict resolution (multiple agents, priority ordering, stock depletion)
- [x] 4.7 Test AcceptOrder conflict resolution (multiple agents, priority wins)
- [x] 4.8 Test trade lifecycle: propose → accept → items exchanged
- [x] 4.9 Test NPC sell resolution with supply-responsive pricing
- [x] 4.10 Test determinism: same seed produces identical results
- [x] 4.11 Test fixed-supply invariant holds after mixed action resolution
- [x] 4.12 Test edge cases: zero-balance trades, self-trades, trades with dead agents, empty treasury
