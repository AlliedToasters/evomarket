## Why

The action system is the interface between agent decision-making and the world simulation. Without a defined vocabulary of actions, validation rules, and resolution logic, the tick engine has no way to process agent decisions. This is the next foundational piece needed to build the game loop on top of the core data models.

## What Changes

- Define all agent action types as Pydantic models inheriting from a common `BaseAction`
- Define `AgentTurnResult` to capture each agent's chosen action plus optional scratchpad edit
- Implement per-action validation rules that reject invalid actions as `IdleAction` with warnings
- Implement deterministic conflict resolution using priority ordering from the world RNG
- Define `ActionResult` to describe the outcome of each resolved action
- Provide `resolve_actions()` as the main entry point for the tick engine

## Capabilities

### New Capabilities
- `action-types`: All agent action type definitions (Move, Harvest, PostOrder, AcceptOrder, ProposeTrade, AcceptTrade, SendMessage, UpdateWill, Inspect, Idle) and the BaseAction/AgentTurnResult/ActionResult models
- `action-validation`: Per-action validation rules that check preconditions against world state, converting invalid actions to IdleAction
- `action-resolution`: Deterministic conflict resolution via RNG-based priority ordering, resolving all actions for a tick and producing ActionResult list

### Modified Capabilities

_(none — existing specs are unchanged)_

## Impact

- **New files:** `evomarket/engine/actions.py`, `tests/test_actions.py`
- **Dependencies:** Imports from `core.world` (WorldState, Node), `core.agent` (Agent), `core.resources` (CommodityType)
- **Downstream:** The tick engine (`engine/tick.py`) will call `resolve_actions()` during the VALIDATE → RESOLVE phases
