# Proposal: Simulation Runner and Heuristic Agents

## Change ID
`simulation-runner`

## Summary
Implement the simulation orchestration layer (run episodes, manage configuration, checkpoint state) and a set of heuristic agents for Phase 0 validation. This is the top-level entry point that ties everything together and proves the game works.

## Motivation
The game engine components are meaningless without something driving them. The simulation runner executes episodes, and heuristic agents provide a fast, deterministic way to validate that the economy functions — agents can survive, trade emerges, wealth distributes, and the system doesn't degenerate.

## What's Changing

### New Files
- `evomarket/simulation/runner.py` — Episode execution, main loop
- `evomarket/simulation/config.py` — SimulationConfig with all parameters
- `evomarket/simulation/metrics.py` — Metric collection, aggregation, export
- `evomarket/simulation/logging.py` — SQLite event logging
- `evomarket/agents/base.py` — Abstract agent interface
- `evomarket/agents/random_agent.py` — Random action selection
- `evomarket/agents/heuristic_agent.py` — Simple strategy agents
- `evomarket/cli.py` — Command-line interface for running simulations
- `tests/test_runner.py`
- `tests/test_heuristic_agents.py`

### SimulationConfig

Single configuration object that holds all game parameters:

```python
@dataclass
class SimulationConfig:
    # World
    seed: int = 42
    num_nodes: int = 15
    num_commodity_types: int = 4
    total_credit_supply: float = 10_000

    # Economy
    survival_tax: float = 1.0
    starting_credits: float = 30.0
    npc_base_price: float = 5.0
    npc_stockpile_capacity: int = 50
    npc_budget_replenish_rate: float = 5.0
    npc_stockpile_decay_rate: float = 0.1
    treasury_min_reserve: float = 100.0
    resource_spawn_rate: float = 0.5
    node_resource_cap: int = 20

    # Population
    population_size: int = 20
    spawn_grace_period: int = 5
    max_spawns_per_tick: int = 3
    min_population_floor: int = 5

    # Trading
    max_open_orders: int = 5
    max_pending_trades: int = 3
    trade_proposal_expiry: int = 10  # ticks

    # Death
    death_treasury_return_pct: float = 0.5
    death_local_share_pct: float = 0.5

    # Simulation
    ticks_per_episode: int = 500
    checkpoint_interval: int = 50  # save state every N ticks
    mode: Literal["synchronous", "asynchronous"] = "synchronous"

    # Debug
    verify_invariant_every_phase: bool = False
    verbose_logging: bool = False
```

Serializable to/from JSON and TOML.

### Simulation Runner

`run_episode(config: SimulationConfig, agent_factory: AgentFactory) -> EpisodeResult`

Main loop:
1. Generate world from config + seed
2. Spawn initial population of agents
3. For each tick up to ticks_per_episode:
   a. Collect agent decisions (via agent interface)
   b. Execute tick
   c. Record metrics
   d. Checkpoint if at interval
   e. Check for termination conditions (all agents dead, etc.)
4. Calculate final fitness scores (net worth)
5. Return EpisodeResult

**EpisodeResult:**
- `config: SimulationConfig`
- `final_world_state: WorldState`
- `tick_metrics: list[TickMetrics]`
- `agent_summaries: list[AgentSummary]`
- `episode_metrics: EpisodeMetrics`

**AgentSummary:**
- `agent_id: str`
- `final_credits: float`
- `final_inventory: dict`
- `final_net_worth: float` (credits + commodity liquidation value)
- `lifetime: int`
- `total_trades: int`
- `total_messages: int`
- `cause_of_death: str | None`
- `prompt_document_at_death: str | None`

**EpisodeMetrics:**
- `mean_lifetime: float`
- `max_lifetime: int`
- `mean_net_worth: float`
- `max_net_worth: float`
- `total_trades: int`
- `total_deaths: int`
- `final_gini: float`
- `final_treasury: float`
- `credits_destroyed_total: float` (commodities lost on death)

### Agent Interface

**BaseAgent (abstract):**
```python
class BaseAgent(ABC):
    @abstractmethod
    def decide(self, observation: AgentObservation) -> AgentTurnResult:
        """Given an observation, return an action and optional prompt edit."""
        ...

    @abstractmethod
    def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
        """Called when the agent is created."""
        ...
```

**AgentFactory:**
```python
class AgentFactory(ABC):
    @abstractmethod
    def create_agent(self, agent_id: str) -> BaseAgent:
        ...
```

### Random Agent

Selects a uniformly random valid action each tick. Used for baseline testing and invariant validation.

- Filters available actions based on current state (can't move if no adjacent nodes accessible, etc.)
- Assigns random parameters to actions (random node for move, random commodity for harvest, etc.)
- Never edits prompt document

### Heuristic Agents

Multiple simple strategies to create a diverse economy:

**HarvesterAgent:** Moves to a resource node, harvests until inventory is full or node is depleted, sells to NPC, repeats. Minimal trading. Tests the basic harvest → sell → survive loop.

**TraderAgent:** Moves between nodes looking for price differentials. Buys low at NPC-saturated nodes (where other agents have been selling), moves to depleted nodes, sells high to NPC. Tests spatial arbitrage.

**SocialAgent:** Stays at high-traffic nodes, posts aggressive buy/sell orders, and sends trade proposals to agents it encounters. Tests the P2P trading system.

**HoarderAgent:** Accumulates commodities and credits, rarely trades, updates will to name nearby agents. Tests the inheritance system and wealth accumulation.

**ExplorerAgent:** Moves frequently, inspects agents, sends broadcast messages about what it finds. Tests communication and information gathering.

Each heuristic agent should be configurable (e.g., how aggressive its pricing is, how often it moves).

### Logging

`EventLogger` — writes to SQLite database:
- Table: `ticks` (tick_number, timestamp, metrics_json)
- Table: `actions` (tick, agent_id, action_type, action_json, success, details)
- Table: `trades` (tick, buyer_id, seller_id, trade_type, items_json, credits)
- Table: `deaths` (tick, agent_id, estate_json, will_json)
- Table: `messages` (tick, sender_id, recipient, node_id, text)
- Table: `agent_snapshots` (tick, agent_id, credits, inventory_json, location, age)

Writes are batched per tick for performance.

### CLI

```bash
# Run a single episode with default config
python -m evomarket run

# Run with custom config
python -m evomarket run --config my_config.toml

# Run with specific seed
python -m evomarket run --seed 123

# Run in hyperfast mode (no verbose logging, no checkpoints)
python -m evomarket run --fast

# Analyze a completed episode
python -m evomarket analyze results/episode_001.sqlite

# Resume from checkpoint
python -m evomarket resume checkpoint_tick_250.json
```

## Acceptance Criteria
- Full episode runs to completion (500 ticks) without crashes or invariant violations
- With 20 heuristic agents, some agents survive the full episode and some die (economy is neither trivially easy nor impossible)
- Trade volume is non-zero (agents actually trade with each other, not just NPCs)
- NPC prices fluctuate in response to agent activity
- Treasury balance stays above minimum reserve (economy is circulating)
- Gini coefficient changes over time (wealth isn't perfectly flat)
- Hyperfast mode runs ≥1000 ticks/second with 20 agents
- All events are logged to SQLite and queryable
- Config is fully serializable and reproducible
- Random seed produces identical results across runs

## Dependencies
- All previous proposals (this is the top-level integration)

## Estimated Complexity
High. ~400-500 lines runner, ~200-300 config, ~300-400 metrics/logging, ~500-700 heuristic agents, ~400-500 tests.

## Validation Goals for Phase 0

After this component is complete, we should be able to answer:
1. Do the economic parameters produce a functioning economy? (agents survive, trade, die naturally)
2. Is the fixed-supply invariant maintained across full episodes?
3. Does spatial structure matter? (do agents cluster, form trade routes, exploit location?)
4. Do different heuristic strategies produce different outcomes? (is the fitness landscape non-trivial?)
5. Does the persistent world state create meaningfully different conditions across episodes?
