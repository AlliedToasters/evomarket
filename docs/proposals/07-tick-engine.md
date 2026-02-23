# Proposal: Tick Engine

## Change ID
`tick-engine`

## Summary
Implement the 10-phase tick resolution pipeline that orchestrates all game mechanics into a single deterministic tick cycle. This is the central integration point that calls into all other subsystems.

## Motivation
The tick engine is the heartbeat of the simulation. It must enforce strict phase ordering, ensure the fixed-supply invariant holds after every tick, and be fast enough for hyperfast execution with heuristic agents (thousands of ticks/second).

## What's Changing

### New Files
- `evomarket/engine/tick.py` — Tick pipeline, phase execution
- `evomarket/engine/observation.py` — Agent context/observation generation
- `tests/test_tick.py`
- `tests/test_invariants.py` — Property-based tests for full tick cycles

### Tick Pipeline

`execute_tick(world: WorldState, agent_decisions: Callable) -> TickResult`

The `agent_decisions` parameter is a callable that takes an observation dict and returns actions. This decouples the tick engine from any specific agent implementation (heuristic, LLM, random).

```
Phase 1:  RECEIVE     — deliver_pending_messages(world)
Phase 2:  OBSERVE     — observations = generate_observations(world)
Phase 3:  DECIDE      — actions, prompt_edits = agent_decisions(observations)
Phase 4:  VALIDATE    — validated = validate_actions(world, actions)
Phase 5:  RESOLVE     — results = resolve_actions(world, validated)
Phase 6:  TAX         — tax_results = collect_all_taxes(world)
Phase 7:  DEATH       — death_results = resolve_deaths(world, dead_agents)
Phase 8:  SPAWN       — spawn_results = spawn_replacements(world)
Phase 9:  REPLENISH   — replenish_npc_budgets(world); regenerate_resources(world); decay_npc_stockpiles(world)
Phase 10: LOG         — log_tick(world, all_results)
```

After each phase, call `world.verify_invariant()` in debug mode. In production/hyperfast mode, verify only at end of tick.

### Phase Implementations

**RECEIVE:** Call `communication.deliver_pending_messages(world)`.

**OBSERVE:** Generate per-agent observation dicts containing:
- Immutable preamble (game rules, tick count, context budget, scratchpad token count)
- Agent's prompt document (scratchpad)
- Agent's state: location, credits, inventory, age, grace ticks remaining
- Node info: node name, type, adjacent nodes, NPC prices, resource availability
- Agents at current node: IDs, display names, ages
- Posted orders at current node
- Messages received this tick
- Pending trade proposals received
- Agent's own posted orders (all nodes) and pending outgoing proposals
- Agent's will

**DECIDE:** Pass observations to the agent_decisions callable. Receive back a dict mapping agent_id → AgentTurnResult(action, prompt_edit). Apply prompt edits immediately to agent prompt_documents.

**VALIDATE:** For each action, run validation rules from the action system. Invalid actions → IdleAction + warning log.

**RESOLVE:** Call `actions.resolve_actions(world, validated_actions)`. This handles movement (+ order suspend/reactivate), harvesting, order posting/acceptance, P2P trade proposals/acceptance, messages (added to pending queue), will updates, and inspect results.

**TAX:** For each living agent (excluding those in grace period): call `economy.collect_tax(world, agent_id, survival_tax)`. Track which agents now have balance ≤ 0.

**DEATH:** Collect all agents with balance ≤ 0. Call `inheritance.resolve_deaths(world, dead_agent_ids)`. This handles will execution, estate distribution, order cleanup, and message cleanup.

**SPAWN:** If population < target (synchronous: no spawns mid-episode; async: spawn replacements). Call `spawning.spawn_agent(world)` for each needed replacement, up to max_spawns_per_tick. Each spawn draws starting_credits from treasury via `economy.fund_spawn()`.

**REPLENISH:** Three sub-operations:
1. `economy.replenish_npc_budgets(world)` — treasury → node budgets
2. `regenerate_resources(world)` — increment node resource stockpiles by spawn rate, capped at resource_cap
3. `economy.decay_npc_stockpiles(world)` — reduce NPC stockpiles to allow price recovery

**LOG:** Record tick number, all action results, deaths, spawns, economic metrics, invariant check.

### Resource Regeneration

`regenerate_resources(world: WorldState) -> None`
- For each RESOURCE node: add `resource_spawn_rate` to each commodity's stockpile (weighted by distribution)
- Cap at `resource_cap`
- This is fractional — 0.5 rate means every 2 ticks a full unit appears

### Observation Generation

`generate_observations(world: WorldState) -> dict[str, AgentObservation]`

**AgentObservation** is a structured object (not raw text — text rendering is the agent interface's job):
- `preamble: PreambleData` (game rules reference, tick, budget info)
- `prompt_document: str`
- `prompt_document_tokens: int`
- `agent_state: AgentStateView` (location, credits, inventory, age, grace)
- `node_info: NodeView` (name, type, adjacencies, NPC prices, resource levels)
- `agents_present: list[AgentPublicView]` (id, display_name, age)
- `posted_orders: list[OrderView]`
- `messages_received: list[MessageView]`
- `pending_proposals: list[TradeProposalView]`
- `own_orders: list[OrderView]`
- `own_will: dict[str, float]`

### TickResult
- `tick: int`
- `action_results: list[ActionResult]`
- `tax_results: list[TaxResult]`
- `death_results: list[DeathResult]`
- `spawn_results: list[SpawnResult]`
- `replenish_result: ReplenishResult`
- `metrics: TickMetrics` (aggregate stats for this tick)
- `invariant_check: bool`

### TickMetrics
- `total_credits_in_circulation: float`
- `agent_credit_gini: float`
- `total_trade_volume: float`
- `trades_executed: int`
- `agents_alive: int`
- `agents_died: int`
- `agents_spawned: int`
- `total_resources_harvested: int`
- `total_npc_sales: int`
- `total_messages_sent: int`

## Acceptance Criteria
- Tick phases execute in strict order (1-10), no phase skipping
- The agent_decisions callable is the only external dependency — tick engine works with any agent implementation
- Fixed-supply invariant holds after every complete tick
- Deterministic: same seed + same agent decisions = identical TickResult
- Hyperfast mode: ≥1000 ticks/second with 20 heuristic agents on a single CPU core
- All results are captured in TickResult for logging and analysis
- Phase-level invariant checking available in debug mode
- Observation generation produces correct, complete views per the information model

## Dependencies
- `core-data-models`
- `action-system`
- `npc-economy`
- `trading-system`
- `communication-system`
- `inheritance-system`

**This component integrates all others. It should be implemented after the subsystems are complete and individually tested.**

## Estimated Complexity
High. ~500-700 lines of tick engine code, ~300-400 for observation, ~600-800 lines of integration tests.
