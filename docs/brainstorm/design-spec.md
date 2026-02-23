# EvoMarket: Design Specification

## Project Overview

EvoMarket is an experimental platform for studying emergent economic behavior in LLM-powered agents. It combines a persistent text-based economy game with an evolutionary optimization framework that uses LoRA adapters as the evolvable genotype.

The platform has two primary research goals:

1. **Environment research**: Understanding what economic strategies and social behaviors emerge when LLM agents interact in a persistent, resource-scarce world.
2. **Neuroevolution research**: Investigating whether evolutionary pressure over LoRA adapter weights can improve agent capabilities in complex, non-differentiable environments — a domain where gradient-based optimization is structurally impossible.

These goals are intentionally decoupled. The game environment should be interesting and well-understood on its own before evolutionary optimization is introduced.

---

## Game World

### Core Concept

A persistent text-based economy where agents harvest resources, trade with each other through natural language negotiation, and must pay a survival cost each tick to remain alive. The world state persists across agent lifetimes, meaning agents inherit economies shaped by their predecessors.

### Currency and Commodities

**Base currency (Credits):** The single unit of account, medium of exchange, and survival currency. Credits are the unambiguous fitness measurement. Agents pay a fixed survival tax in credits each tick. An agent with zero credits dies.

**Commodities:** 3-5 resource types (e.g., Iron, Wood, Stone, Herbs, Crystal). Commodities have no intrinsic survival value — they are only useful through trade. Their value emerges entirely from supply, demand, and spatial distribution.

### World Topology

The world is a **graph of nodes** connected by edges. Target size: 10-20 nodes.

**Node properties:**
- Resource spawn distribution (e.g., Node A: 70% Iron, 20% Stone, 10% nothing)
- Spawn rate (resources regenerate over time, configurable per node)
- Current resource inventory (depleted by harvesting, replenished by spawn rate)
- Node type: Resource node, Trade hub (no resources but high connectivity), Crossroads

**Graph structure:** Not fully random. The topology should create natural trade routes and economic geography:
- Clusters of resource-specialized nodes connected by sparse links
- A few high-connectivity hub nodes that serve as natural marketplaces
- Spatial correlation in resource types (forest region, mountain region, etc.)

**Graph initialization:** Fixed at world creation. The topology does not change during gameplay. Environmental dynamism comes through the resource layer (shifting spawn rates, depletion, events).

### Agent Prompt and Self-Prompting

Each agent has a **mutable prompt document** — a persistent text buffer that the agent sees at the start of every tick, before any world state information. This document serves as the agent's internal strategy, memory, notes, and cognitive scaffolding.

**Seed prompt:** When an agent spawns, its prompt document is initialized with a seed prompt that describes the game rules, the agent's objective (survive and accumulate wealth), and basic strategic guidance. In evolutionary mode, the seed prompt may be inherited from a parent agent.

**Self-prompting (free action):** Each tick, in addition to their main action, agents may freely edit their prompt document. They can append notes, rewrite strategies, track observations about other agents, or delete the entire contents including the original seed. There is no cost or action penalty for editing the prompt.

**What agents see each tick (in order):**
1. **Immutable preamble** (not editable by the agent): Game rules, action reference, the agent's objective, context window limit, truncation policy, and a **live token count** of the agent's current prompt document (e.g., `Scratchpad: 1,847 / 12,000 tokens`). This gives agents a directional signal for managing context bloat without requiring them to estimate it. This block is always preserved regardless of context pressure.
2. Their self-authored prompt document (mutable, persistent across ticks)
3. World state information they are entitled to per the information model (location, inventory, balance, visible agents, messages received, posted orders, etc.)
4. A request to choose one action for the tick

**Context window management:** Each model has a hard context window limit determined by the inference system. The agent is informed of this limit in the immutable preamble. When the total context (preamble + prompt document + world state + action request) exceeds the window, the prompt document is truncated using a **last-n policy**: the most recent content is preserved, older content is dropped. The immutable preamble and world state are never truncated.

This creates natural selection pressure on note-taking quality. Agents that maintain concise, well-organized prompt documents retain full context. Agents that write bloated or unfocused notes lose older information to truncation. Agents that periodically consolidate and prune their notes demonstrate a meaningful cognitive capability. No artificial limits are imposed — the context window itself is the constraint, and managing it is part of the game.

**Design implications:** The prompt document is a form of external memory that the agent fully controls. Agents can use it to maintain state that would otherwise be lost between ticks (since LLM context is reset each tick). It also means that agent behavior is shaped by two factors: the model weights (or LoRA adapter) and the accumulated prompt document. Both can drift over an agent's lifetime.

### Agent Actions

Each tick, every agent submits exactly one action (plus optional free prompt edits). All actions resolve simultaneously.

| Action | Description |
|---|---|
| `move <node>` | Move to an adjacent node. Takes one tick. |
| `harvest` | Gather a resource at current node (random draw from node's distribution). Produces one commodity unit. |
| `post_order <buy/sell> <commodity> <quantity> <price>` | Post a public trade order visible to all agents at the current node. |
| `accept_order <order_id>` | Accept an existing posted order, executing the trade. |
| `propose_trade <agent> <offer> <request>` | Propose a private P2P trade to a specific agent at the same node. |
| `accept_trade <trade_id>` | Accept a pending P2P trade proposal. |
| `send_message <agent/all> <text>` | Send a natural language message to a specific agent at the same node, or broadcast to all agents at the node. |
| `update_will <distribution>` | Update the agent's public will (see Inheritance below). |
| `inspect <agent>` | Observe another agent at the same node (reveals partial information). |
| `idle` | Do nothing. Still pays survival tax. |

**Free actions (no tick cost):** Editing the agent's prompt document is always free and accompanies any main action.

**Conflict resolution:** When multiple agents attempt incompatible actions in the same tick (e.g., two agents harvesting the last resource unit at a node), priority is assigned randomly each tick.

### Information Model

**Public information (visible to all):**
- World graph topology and node types
- Which agents are at each node
- Posted trade orders at the current node
- Agent wills
- Agent age (ticks survived)

**Observable information (requires same node + inspect action):**
- That another agent possesses items (but not exact types or quantities)
- Approximate wealth tier (poor / moderate / wealthy) — not exact balance

**Private information (only the agent knows):**
- Exact inventory contents and quantities
- Exact credit balance
- Pending trade proposals received

**Voluntary disclosure:**
- Agents can reveal specific inventory items through messages ("I have 3 Iron, want to trade?")
- Truthfulness is not enforced — agents can lie in messages
- Executed trades are logged and visible at the node (so reputation can be inferred from trade history)

### Communication

Agents can send natural language messages as their action for a tick. Messages are delivered to the recipient(s) at the start of the next tick.

**Communication costs:** Sending a message consumes the agent's action for that tick but does not cost credits. This creates a natural tradeoff — time spent negotiating is time not spent harvesting or moving.

**Message scope:** Messages are only deliverable to agents at the same node. There is no long-distance communication. This creates information locality and makes physical position strategically important.

### Survival Mechanics

**Survival tax:** Each tick, every agent pays a fixed cost in credits. If an agent cannot pay, it dies immediately.

**Starting endowment:** New agents spawn with a fixed number of credits and no commodities. The endowment should be enough to survive approximately 20-50 ticks without any income, creating urgency without instant death.

**Death:** When an agent dies, its inventory and remaining credits are distributed according to the inheritance system.

### Inheritance System

Each agent maintains a **public will** — a document visible to all agents that specifies how the agent's estate should be distributed upon death.

**Will format:** A list of (beneficiary_agent, percentage) pairs. Percentages need not sum to 100% — any remainder goes to the default redistribution pool.

**Death resolution order:**
1. Execute will allocations to living beneficiaries.
2. Any unclaimed portion (beneficiaries who have died, or unallocated percentage) enters the redistribution pool.
3. Redistribution pool is split:
   - **Local share (configurable, e.g., 50%):** Divided evenly among all living agents at the same node as the deceased.
   - **Destroyed (configurable, e.g., 50%):** Removed from the economy permanently (deflationary sink).

**Will updates:** Updating a will costs one tick's action. Wills are public and readable by any agent.

**Strategic implications:** Wills can be used as leverage in negotiations ("trade with me and I'll name you in my will"), as alliance-forming tools, and as incentive structures. Because wills are public, promises are verifiable.

---

## Execution Modes

### Synchronous Mode (Phase 1)

Standard generational evolution. A fixed population of agents plays the game for a set number of ticks. At the end of the episode:
- Agents are ranked by credits (the fitness function)
- Top performers are selected for reproduction
- New population is generated via crossover and mutation of LoRA adapters
- World state carries forward to the next generation (partial persistence with configurable decay)

This mode is simpler to implement and analyze. Use it to validate the game mechanics, tune parameters, and establish baselines.

### Asynchronous Mode (Phase 2)

Steady-state evolution. No discrete generations. Agents have continuous lifetimes determined by their economic viability:
- When an agent dies (runs out of credits), a replacement spawns
- The replacement's LoRA is derived from the current living population (tournament selection weighted by age and/or wealth, with mutation)
- The world runs continuously with overlapping agent lifetimes
- Selection pressure is embedded in the environment rather than applied externally

This mode is more biologically realistic and creates richer dynamics but is harder to analyze and debug.

---

## World Persistence

The game world state persists across agent lifetimes (and across generations in synchronous mode). This is a core design feature — agents inherit economies shaped by their predecessors.

**What persists:**
- Node resource levels (depletion and regeneration)
- Posted trade orders
- Trade history / reputation data
- Total currency in circulation

**Configurable decay (synchronous mode between generations):**
- Resource regeneration rate between generations (how much nodes recover)
- Currency redistribution (does accumulated wealth carry over, or partially reset?)
- Order book clearing (stale orders may be removed)

**Economic balance levers:**
- Survival tax rate (controls how fast credits drain)
- Resource spawn rates (controls income)
- Destruction percentage on death (controls inflation/deflation)
- Starting endowment for new agents

---

## Technical Architecture

### Game Server

A lightweight Python server managing world state and action resolution.

**Requirements:**
- Fast enough for hyperfast execution (thousands of ticks/second without LLM in the loop, for simulation testing and parameter tuning)
- Clean separation between world simulation and agent interface
- Full game state serializable/deserializable for persistence, checkpointing, and analysis
- Deterministic given a fixed random seed (for reproducibility)
- Comprehensive logging of all actions, trades, messages, deaths, and state transitions

### Agent Interface

A text-based API that each agent (LLM) interacts with. Each tick, the agent receives (in order):
1. Its own mutable prompt document (self-authored, persistent across ticks)
2. A text description of its current state (location, inventory, balance, age)
3. Visible information about the current node (other agents present, posted orders, recent messages received)
4. A request to choose an action and optionally provide prompt document edits

The agent responds with a single action string and an optional prompt edit payload. The interface validates the action and submits it to the game server.

### OpenClaw Integration

Each agent is an OpenClaw instance configured with:
- The game interface exposed as MCP tools (one tool per action type, plus a prompt edit tool)
- A messaging channel connected to the game's communication system
- The agent's mutable prompt document injected as the system prompt (updated each tick with the agent's latest edits)
- World state context appended after the prompt document each tick

### Evolutionary Framework (Phase 2)

Manages the population of LoRA adapters:
- Population storage and versioning
- Selection operators (tournament, fitness-proportional)
- Crossover operators (per-layer, per-rank-component)
- Mutation operators (Gaussian noise, configurable magnitude)
- Fitness tracking and genealogy logging

---

## Configurable Parameters

| Parameter | Description | Suggested Starting Value |
|---|---|---|
| `num_nodes` | World graph size | 15 |
| `num_commodity_types` | Distinct resource types | 4 |
| `survival_tax` | Credits consumed per tick | 1 |
| `starting_credits` | Credits given to new agents | 30 |
| `harvest_yield_credits` | Not applicable — harvesting yields commodities, not credits | — |
| `resource_spawn_rate` | Units regenerated per node per tick | 0.5 |
| `node_resource_cap` | Max stockpile at a node before spawning stops | 20 |
| `death_destruction_pct` | % of estate destroyed on death | 50% |
| `death_local_share_pct` | % of estate distributed to agents at same node | 50% |
| `population_size` | Number of agents in the world | 20 |
| `ticks_per_episode` | Episode length (synchronous mode) | 500 |
| `message_limit_per_tick` | Max messages an agent can include in a message action | 1 |
| `max_pending_trades` | Max open P2P trade proposals per agent | 3 |

---

## Metrics and Observability

### Per-Tick Metrics
- Total credits in circulation
- Gini coefficient of wealth distribution
- Trade volume (number and value of executed trades)
- Resource levels across all nodes
- Agent deaths and spawns

### Per-Agent Metrics
- Lifetime (ticks survived)
- Total credits earned / spent
- Trade count and net trade value
- Movement patterns (nodes visited)
- Communication volume
- Inventory diversity
- Prompt document length and edit frequency
- Prompt document at death (archived for analysis)

### Per-Generation Metrics (Synchronous Mode)
- Fitness distribution (min, max, mean, median, variance)
- Strategy diversity (behavioral clustering)
- Economic state at generation boundary
- Genealogy and lineage tracking

### Emergent Behavior Detection
- Trade network analysis (who trades with whom, formation of cliques)
- Spatial patterns (do agents specialize by region?)
- Communication analysis (common negotiation patterns, deception detection)
- Will network analysis (inheritance chains, alliance structures)
- Price convergence (do stable market prices emerge?)
- Prompt document clustering (do successful agents develop similar self-prompting strategies?)
- Strategy drift (how do agents' prompt documents evolve over their lifetimes?)

---

## Development Phases

### Phase 0: Game Server Prototype
Build the core game simulation without any LLM integration. Validate mechanics using random agents or simple heuristic agents. Tune economic parameters for interesting dynamics (agents shouldn't die instantly or live forever without effort).

### Phase 1: LLM Integration + Synchronous Evolution
Connect the game to LLM agents via OpenClaw / direct API. Run the game with small open-weight models (7B-8B) and fixed weights (no evolution). Validate that LLM agents can play the game coherently. Then introduce the evolutionary loop with synchronous generations.

### Phase 2: Asynchronous Evolution + Scale
Switch to asynchronous lifecycle mode. Scale up model size. Introduce LoRA evolution. Run longer experiments with larger populations.

### Phase 3: Complexity Expansion
Add game features (crafting, events, etc.) based on findings from earlier phases. Consider more complex environments (Minecraft integration as stretch goal).
