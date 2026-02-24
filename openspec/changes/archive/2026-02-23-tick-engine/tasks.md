## 1. Data Models

- [x] 1.1 Add observation models to `evomarket/engine/observation.py`: `PreambleData`, `AgentStateView`, `NodeView`, `AgentPublicView`, `OrderView`, `MessageView`, `TradeProposalView`, `AgentObservation`
- [x] 1.2 Add tick result models to `evomarket/engine/tick.py`: `SpawnResult`, `TickMetrics`, `TickResult`, `TickPhase` enum

## 2. Observation Generation

- [x] 2.1 Implement `generate_observations(world) -> dict[str, AgentObservation]` in `evomarket/engine/observation.py`
- [x] 2.2 Write tests for observation generation in `tests/test_observation.py`: agent state view, node info with NPC prices, agents present, posted orders, messages received, pending proposals, own orders/proposals, will

## 3. Resource Regeneration and Spawning

- [x] 3.1 Implement `regenerate_resources(world)` in `evomarket/engine/tick.py`: fractional accumulation per node, capped at resource_cap
- [x] 3.2 Implement `spawn_agents(world) -> list[SpawnResult]` in `evomarket/engine/spawning.py`: treasury-funded, deterministic IDs, SPAWN node location, grace period
- [x] 3.3 Write tests for resource regeneration in `tests/test_tick.py`: accumulation rate, cap behavior, fractional values, non-resource nodes skipped
- [x] 3.4 Write tests for agent spawning in `tests/test_spawning.py`: funding, ID assignment, initialization, treasury exhaustion

## 4. Tick Pipeline

- [x] 4.1 Implement `execute_tick(world, agent_decisions, debug=False) -> TickResult` in `evomarket/engine/tick.py` with all 10 phases
- [x] 4.2 Implement TAX phase: grace period decrement, tax collection, death identification
- [x] 4.3 Implement DEATH phase: death resolution with order cancel and message cleanup callbacks
- [x] 4.4 Implement SPAWN phase: population check, spawn calls
- [x] 4.5 Implement REPLENISH phase: NPC budget replenish, resource regeneration, stockpile decay
- [x] 4.6 Implement LOG phase: age increment, metrics computation (Gini coefficient, trade volume, harvest counts)
- [x] 4.7 Implement debug-mode per-phase invariant checking and end-of-tick invariant check

## 5. Integration Tests

- [x] 5.1 Write integration test: full tick with all phases executing in order
- [x] 5.2 Write integration test: agent death → spawn cycle across a single tick
- [x] 5.3 Write integration test: determinism — same seed + same decisions = identical TickResult
- [x] 5.4 Write integration test: fixed-supply invariant holds after multi-tick sequences
- [x] 5.5 Write integration test: debug mode verifies invariant after each phase
- [x] 5.6 Update `tests/test_invariants.py` with property-based tests for full tick cycles
