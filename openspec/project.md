# EvoMarket

## Project Description

EvoMarket is an experimental platform combining a persistent text-based economy game with an evolutionary optimization framework. LLM-powered agents interact in a resource-scarce world, trading commodities, negotiating in natural language, and paying survival taxes to stay alive. The platform supports both synchronous (generational) and asynchronous (steady-state) evolutionary modes, with LoRA adapters as the evolvable genotype.

The current development phase is **Phase 0**: building and validating the core game simulation with heuristic/random agents before any LLM or evolutionary integration.

## Tech Stack

- **Language:** Python 3.12+
- **Game server:** Pure Python, no framework. Lightweight, fast, deterministic.
- **Data models:** Pydantic v2 for validation and serialization
- **Persistence:** JSON serialization for world state checkpoints. SQLite for event logs and metrics.
- **Testing:** pytest with hypothesis for property-based testing of economic invariants
- **Visualization:** matplotlib for metrics plots during development. Optional: streamlit dashboard later.
- **Package management:** uv
- **Linting/formatting:** ruff
- **Type checking:** pyright (strict mode)

## Architecture

```
evomarket/
├── core/                  # Core data models and types
│   ├── world.py           # World, Node, Edge definitions
│   ├── agent.py           # Agent state, inventory, balance
│   ├── resources.py       # Commodity types, resource spawning
│   └── economy.py         # Currency, treasury, NPC pricing
├── engine/                # Game execution engine
│   ├── tick.py            # Tick phase resolution (10-phase pipeline)
│   ├── actions.py         # Action types, validation, resolution
│   ├── trading.py         # Order book, P2P trades, order lifecycle
│   ├── communication.py   # Message passing, delivery
│   ├── inheritance.py     # Will system, death resolution, estate distribution
│   └── spawning.py        # Agent spawn logic, location selection
├── agents/                # Agent implementations
│   ├── base.py            # Abstract agent interface
│   ├── random_agent.py    # Random action selection (for testing)
│   ├── heuristic_agent.py # Simple strategy agents (for Phase 0 validation)
│   └── llm_agent.py       # LLM-backed agent (Phase 1, stub for now)
├── simulation/            # Simulation orchestration
│   ├── runner.py          # Main simulation loop
│   ├── config.py          # Simulation parameters and configuration
│   ├── metrics.py         # Per-tick, per-agent, aggregate metrics
│   └── logging.py         # Event logging to SQLite
├── visualization/         # Analysis and visualization
│   ├── dashboard.py       # Metrics dashboard
│   └── plots.py           # Standard analysis plots
└── tests/
    ├── test_world.py
    ├── test_tick.py
    ├── test_trading.py
    ├── test_economy.py
    ├── test_inheritance.py
    ├── test_invariants.py  # Property-based tests for economic invariants
    └── conftest.py         # Shared fixtures (world configs, agent factories)
```

## Key Architectural Decisions

### Fixed Money Supply
The total credits in the system are constant. Credits circulate between three reservoirs: agent balances, NPC node budgets, and the world treasury. No credits are ever created or destroyed. The survival tax pumps credits from agents to the treasury; NPC buy orders return credits from node budgets to agents; the treasury replenishes node budgets. Starting endowments for new agents are drawn from the treasury.

**Critical invariant:** `sum(agent_balances) + sum(npc_budgets) + treasury = TOTAL_SUPPLY` must hold at every tick. This invariant must be tested after every state mutation.

### Deterministic Simulation
Given a fixed random seed, the simulation produces identical results. All randomness flows through a single seeded RNG. This is essential for reproducibility, debugging, and meaningful A/B comparisons.

### Strict Tick Phase Ordering
Each tick resolves in 10 phases in strict order: RECEIVE → OBSERVE → DECIDE → VALIDATE → RESOLVE → TAX → DEATH → SPAWN → REPLENISH → LOG. No phase may access state that another phase is responsible for mutating.

### Supply-Responsive NPC Pricing
NPC buy prices follow: `price = base_price * (1 - stockpile / capacity)`. High stockpile = low price. Depleted stockpile = high price. NPCs only buy their node's native commodity types.

### Agent Prompt Architecture
Agents see (in order): immutable preamble (game rules, token budget), mutable scratchpad (self-authored, persistent across ticks), world state, action request. The scratchpad is subject to last-n truncation when context exceeds the model's window. Editing the scratchpad is a free action.

## Conventions

### Code Style
- All public functions and classes have docstrings
- Type hints on all function signatures
- No `Any` types except in serialization boundaries
- Prefer dataclasses/Pydantic models over raw dicts
- Immutable data where possible; mutations happen only in designated engine phases

### Naming
- Files: snake_case
- Classes: PascalCase
- Functions/methods: snake_case
- Constants: UPPER_SNAKE_CASE
- Agent IDs: `agent_{zero_padded_number}` (e.g., `agent_042`)
- Node IDs: `node_{name}` (e.g., `node_iron_peak`, `node_trade_hub`)

### Testing
- Every module has a corresponding test file
- Economic invariants (fixed supply, non-negative balances) are tested as property-based tests that run after arbitrary action sequences
- Use fixtures for standard world configurations (small 5-node test world, full 15-node world)
- Test edge cases explicitly: zero balance + tax, simultaneous conflicting trades, death during trade, empty treasury

### Error Handling
- Invalid agent actions become `idle` — never crash the simulation
- Log warnings for invalid actions (useful for debugging agent behavior)
- Assertions for invariant violations (these indicate bugs, not gameplay)

### Git
- `main` branch is always passing tests
- Feature branches via worktrees for parallel development
- Commit messages: `component: brief description` (e.g., `engine: implement tick phase resolution`)
- PR descriptions reference the OpenSpec change ID

## Parameters (Starting Defaults)

| Parameter | Value | Notes |
|---|---|---|
| `total_credit_supply` | 10,000 | Fixed, never changes |
| `num_nodes` | 15 | Graph size |
| `num_commodity_types` | 4 | Iron, Wood, Stone, Herbs |
| `survival_tax` | 1 credit/tick | Per-agent per-tick cost |
| `starting_credits` | 30 | Drawn from treasury on spawn |
| `resource_spawn_rate` | 0.5 units/node/tick | Fractional accumulates |
| `node_resource_cap` | 20 | Max stockpile before spawning stops |
| `npc_base_price` | 5 credits | Per commodity, may vary by node |
| `npc_stockpile_capacity` | 50 | Controls price sensitivity |
| `npc_budget_replenish_rate` | configurable | Credits/tick from treasury to each node |
| `population_size` | 20 | Target agent count |
| `ticks_per_episode` | 500 | Synchronous mode episode length |
| `spawn_grace_period` | 5 ticks | New agents exempt from tax |
| `max_open_orders` | 5 | Per agent across all nodes |
| `max_pending_trades` | 3 | P2P proposals per agent |
| `death_treasury_return_pct` | 50% | Unclaimed estate → treasury |
| `death_local_share_pct` | 50% | Unclaimed estate → local agents |

## External Dependencies (Phase 0)

None beyond standard Python ecosystem. No LLM APIs, no OpenClaw, no GPU requirements. Phase 0 is pure simulation.

## Constraints

- The game server must support "hyperfast" mode: thousands of ticks/second with heuristic agents, for parameter tuning and validation
- All state must be serializable to JSON for checkpointing and analysis
- The simulation must be deterministic given a fixed seed
- The fixed supply invariant must never be violated
