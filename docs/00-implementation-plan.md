# EvoMarket: Implementation Plan

## Proposal Summary

| # | Change ID | Description | Est. Complexity | Dependencies |
|---|---|---|---|---|
| 01 | `core-data-models` | World, agents, resources, economy types | Medium | None |
| 02 | `action-system` | Action types, validation, resolution | Medium-High | 01 |
| 03 | `npc-economy` | NPC pricing, treasury, credit circulation | Medium | 01 |
| 04 | `trading-system` | Order book, P2P trades, settlement | High | 01, (02) |
| 05 | `communication-system` | Message passing, delivery, history | Low-Medium | 01 |
| 06 | `inheritance-system` | Wills, death resolution, estates | Medium-High | 01, (04, 05) |
| 07 | `tick-engine` | 10-phase tick pipeline, observations | High | 01-06 |
| 08 | `simulation-runner` | Runner, heuristic agents, logging, CLI | High | 01-07 |

## Dependency Graph

```
                    ┌──────────────────┐
                    │  01: Core Data   │
                    │     Models       │
                    └──┬──┬──┬──┬──┬──┘
                       │  │  │  │  │
          ┌────────────┘  │  │  │  └────────────┐
          ▼               ▼  │  ▼               ▼
   ┌─────────────┐  ┌───────┐│┌──────────┐ ┌──────────┐
   │ 02: Action  │  │03: NPC│││05: Comms │ │06: Inher.│
   │   System    │  │Economy│││  System  │ │  System  │
   └──────┬──────┘  └───┬───┘│└────┬─────┘ └────┬─────┘
          │              │    │     │             │
          │    ┌─────────┘    │     │             │
          │    │   ┌──────────┘     │             │
          │    │   │  ┌─────────────┘             │
          │    │   │  │    ┌──────────────────────┘
          ▼    ▼   ▼  ▼    ▼
   ┌──────────────────────────────┐
   │  04: Trading System          │
   │  (loose dep on 02 for types) │
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │      07: Tick Engine         │
   │   (integrates all above)     │
   └──────────────┬───────────────┘
                  │
                  ▼
   ┌──────────────────────────────┐
   │   08: Simulation Runner      │
   │   + Heuristic Agents + CLI   │
   └──────────────────────────────┘
```

## Recommended Implementation Order

### Wave 1: Foundation (sequential, one worktree)
**`core-data-models`** — Must come first. Everything depends on it. Implement on `main` directly since there's nothing else to conflict with.

```bash
# No worktree needed — just work on main
cd evomarket
claude
# /openspec:proposal → core-data-models
# /openspec:apply
```

### Wave 2: Subsystems (parallel, multiple worktrees)
Once core data models are merged to main, these can all be developed in parallel:

```bash
# Terminal 1
claude --worktree action-system

# Terminal 2
claude --worktree npc-economy

# Terminal 3
claude --worktree trading-system

# Terminal 4
claude --worktree communication-system

# Terminal 5
claude --worktree inheritance-system
```

These are mostly independent — they all import from `core/` but don't import from each other (inheritance has a loose dependency on trading and communication for death cleanup, but can stub those interfaces).

**Merge strategy:** As each subsystem completes and passes tests, merge to main. Later subsystems should pull from main to pick up earlier merges.

### Wave 3: Integration (sequential, one worktree)
**`tick-engine`** — Integrates all subsystems. Must wait for Wave 2 to complete.

```bash
claude --worktree tick-engine
```

### Wave 4: Top-level (sequential, one worktree)
**`simulation-runner`** — Depends on everything. Implements heuristic agents, CLI, logging.

```bash
claude --worktree simulation-runner
```

## Getting Started

```bash
# 1. Create the repo
mkdir evomarket && cd evomarket
git init

# 2. Set up Python project
uv init
uv add pydantic pytest hypothesis ruff

# 3. Install OpenSpec
npx openspec@latest init
# Select: Claude Code
# When prompted, paste content from openspec-project.md into openspec/project.md

# 4. Create the project structure
mkdir -p evomarket/{core,engine,agents,simulation,visualization} tests

# 5. Start Wave 1
claude
# "Read openspec/project.md and the core-data-models proposal, then implement it"
```

## Phase 0 Exit Criteria

Phase 0 is complete when:
- [ ] A full 500-tick episode runs with 20 heuristic agents without invariant violations
- [ ] Multiple heuristic strategies produce measurably different outcomes
- [ ] The economy is self-sustaining (agents survive through harvesting + trading)
- [ ] Agent deaths occur from poor strategy, not impossible economics
- [ ] NPC prices respond to agent activity (visible price fluctuation)
- [ ] Trade volume between agents is non-trivial
- [ ] The simulation runs at ≥1000 ticks/second in hyperfast mode
- [ ] All events are logged and queryable
- [ ] Economic parameters are documented with rationale for chosen values
- [ ] At least 3 different random seeds produce qualitatively similar (stable) economies

After these criteria are met, the project is ready for Phase 1: LLM agent integration.
