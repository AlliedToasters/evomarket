# EvoMarket: Design Gap Solutions (Draft for Discussion)

## 1. Money Supply and Economic Loop

### The Problem

Credits are the survival currency and fitness measure. Agents harvest commodities. But commodities have no intrinsic demand — no rational agent would trade survival-critical credits for commodities unless commodities can somehow be converted back to credits. Without a credit source beyond the starting endowment, the economy is a countdown timer to universal death.

### Proposed Solution: Fixed Supply with NPC Demand

**Fixed total supply.** A fixed pool of credits exists in the world. No new credits are ever minted. Credits flow between three reservoirs:

1. **Agent balances** — credits held by living agents
2. **NPC buy orders** — credits sitting in standing buy orders at nodes, waiting to be claimed
3. **World treasury** — credits held by the world itself (e.g., unclaimed death estates, initial reserve)

The total across all three reservoirs is constant. Credits are never created or destroyed — they circulate.

**NPC buy orders as the demand sink.** Each resource node posts standing NPC buy orders for its native commodity type. These represent "the world" buying resources. An agent at a Forest node can sell Wood to the NPC order and receive credits. This is how agents convert labor (harvesting) into income (credits).

NPC buy order properties:
- **Price: Supply-responsive.** The NPC buy price for a commodity at a node decreases as the node's stockpile of that commodity increases, and rises as it depletes. This follows a simple curve: `price = base_price * (1 - stockpile / capacity)`. When a node is saturated with a commodity (agents have been selling heavily), the price drops toward zero. When a node's stockpile is empty (high demand, low supply), the price approaches `base_price`. This creates natural boom-bust cycles, incentivizes agents to diversify where they sell, and rewards strategic reasoning about market conditions. If too many agents cluster at one node, prices drop and some are incentivized to move — the pricing mechanism itself acts as a spatial balancing force.
- **Budget:** NPC orders draw from a per-node credit pool that refills from the world treasury at a configurable rate. If agents drain a node's NPC budget, they have to sell elsewhere or wait for it to replenish. This prevents infinite credit extraction from a single node. Budget and price interact: even if a node's price is high, the NPC can't buy if its budget is exhausted.
- **Standing orders only for native commodities.** A Mountain node buys Iron but not Wood. This means agents can't just harvest and sell at the same node for every commodity — spatial trade is still incentivized for non-native commodities.

**Where do NPC credits come from?** The survival tax. When agents pay survival tax, those credits go into the world treasury, which feeds back into NPC node budgets. This closes the loop:

```
Agents pay survival tax → World treasury → NPC node budgets → Agents sell commodities → Agent balances → Survival tax → ...
```

**Why this works with fixed supply:**
- Credits circulate, never created or destroyed
- Survival tax is the pump that moves credits from agents back into the world
- NPC orders are the valve that lets agents earn credits back
- If many agents cluster at one node, they drain its NPC budget and must spread out or trade P2P
- If agents die and their estates are unclaimed, those credits return to the treasury

**Tuning levers:**
- NPC base prices per commodity per node
- NPC stockpile capacity per node (controls price sensitivity — larger capacity means slower price swings)
- Node budget replenishment rate from treasury
- Survival tax rate
- Starting endowment (drawn from treasury at spawn)

**What about death estates?** Under fixed supply, we can't destroy credits on death (that would be deflationary drain toward zero). Instead, the "destruction percentage" from the original spec becomes a "return to treasury" percentage. The local share still goes to nearby agents. So death redistributes credits between agents and the world treasury, but never removes them from existence.

### Alternative Considered: Commodity-as-Rent

Instead of a pure credit survival tax, agents could be required to pay rent in specific commodities (e.g., 1 Food per tick). This creates intrinsic commodity demand without needing NPCs. Rejected for now because it adds complexity — which commodities count, what if you can't find the right type — and because a single credit currency is cleaner for fitness measurement.

### Alternative Considered: Continuous Minting

Mint new credits each tick (e.g., distributed to NPC budgets or as universal basic income). Simpler than fixed supply but inflationary, and makes the total supply a moving target. Fitness comparisons across generations become harder because the credit supply is different. Rejected in favor of fixed supply for cleaner experimental design.

---

## 2. Tick Phase Ordering

### The Problem

The exact sequence of operations within a tick determines edge cases: can an agent spend credits on a trade and then die from tax in the same tick? Do messages arrive before or after actions?

### Proposed Solution: Strict Phase Order

Each tick resolves in the following phases, in order:

```
Phase 1: RECEIVE       — Deliver messages sent last tick. Deliver trade proposals from last tick.
Phase 2: OBSERVE       — Generate each agent's world state view (what they see this tick).
Phase 3: DECIDE        — All agents receive their context and submit actions + prompt edits.
Phase 4: VALIDATE      — Check all submitted actions for legality (can't trade more than you have, can't move to non-adjacent node, etc.). Illegal actions become idle.
Phase 5: RESOLVE       — Execute all valid actions simultaneously with random priority for conflicts.
Phase 6: TAX           — Deduct survival tax from all agents. Taxed credits go to world treasury.
Phase 7: DEATH         — Any agent with balance ≤ 0 dies. Execute wills, redistribute estates.
Phase 8: SPAWN         — Spawn replacement agents (if applicable). New agents draw starting endowment from world treasury.
Phase 9: REPLENISH     — World treasury distributes credits to NPC node budgets. Resource nodes regenerate commodities based on spawn rates.
Phase 10: LOG          — Record all tick events, state transitions, metrics.
```

**Key ordering decisions and rationale:**
- Tax happens AFTER actions resolve, so an agent can execute a profitable trade and use the proceeds to survive that tick. Taxing before actions would kill agents who had viable trades pending.
- Death happens AFTER tax, so agents know exactly when they'll die (when their balance can't cover tax).
- Spawn happens AFTER death, so the population count is updated before new agents enter.
- Replenish happens last, so NPC budgets and resource nodes are refreshed for the next tick.
- Messages have one-tick latency (sent in one tick, delivered at the start of the next). This prevents same-tick negotiation loops and keeps the action economy clean.

---

## 3. Agent Identity

### The Problem

Agents need persistent, recognizable identities for reputation, relationships, wills, and trade history to function.

### Proposed Solution

Each agent gets a unique, persistent identifier assigned at spawn. The identifier consists of:
- **Agent ID:** A unique alphanumeric string (e.g., `agent_042`). Persists for the agent's entire lifetime. Never reused — dead agent IDs are retired. This is the canonical reference used in wills, trade proposals, and system messages.
- **Display name:** Agents can set and change a self-chosen display name as a free action (like prompt edits). Other agents see this name alongside the ID. Name changes are logged and visible in trade history, so agents cannot escape their reputation by renaming — the underlying ID is always visible. This allows agents to use names strategically (e.g., signaling specialization with "IronTrader_42" or rebranding after a failed negotiation) without enabling impersonation or identity laundering.

**Identity across generations (synchronous mode):** Agent IDs reset each generation. There is no persistent identity across generations — only the LoRA adapter and (optionally) the seed prompt carry forward.

**Identity in asynchronous mode:** Agent IDs are globally unique across all time. When a new agent spawns to replace a dead one, it gets a fresh ID. The parent-child lineage is tracked in metadata but not exposed to agents in-game.

---

## 4. Spawn Location

### The Problem

Where new agents appear affects spatial dynamics, early-game competition, and fairness.

### Proposed Solution

New agents spawn at a **designated spawn node** (or one of several spawn nodes for larger maps). Spawn nodes have the following special properties:
- No native resource spawns (agents must move to a resource node to begin harvesting)
- High connectivity (adjacent to multiple regions, so agents can choose a direction)
- Active NPC buy orders for ALL commodity types (so new agents who arrive with commodities from trades can sell them)
- No survival tax for the first N ticks (grace period, configurable — e.g., 5 ticks) to give new agents time to orient and move to a resource node before the clock starts

**Rationale:** A central spawn node with grace period creates a natural "new player experience" without complex tutorial mechanics. Agents must immediately make a strategic decision (which region to move toward) and have a short window to do so without dying.

**Alternative considered:** Random spawn across all nodes. Rejected because it creates extreme luck variance — spawning on a rich, empty node vs. a depleted, crowded one.

---

## 5. Order Lifecycle

### The Problem

Posted trade orders need clear rules for persistence, cancellation, and failure cases.

### Proposed Solution

**Persistence:** Posted orders remain active until explicitly cancelled by the poster, fully filled, or the poster dies. Orders survive across ticks.

**Cancellation:** An agent can cancel their own posted orders as a free action (like prompt edits — no tick cost). This prevents agents from being locked into bad orders.

**Stale order handling:** If an agent moves to a different node, their posted orders at the previous node become **suspended** (invisible to others, not fillable) and automatically reactivate if the agent returns to that node. This prevents remote selling from nodes you've left.

**Insufficient funds:** If a buy order is accepted but the poster's balance has dropped below the order price since posting (due to tax or other trades), the order fails. The accepting agent's action is wasted (becomes idle). To mitigate griefing via fake orders, agents can inspect an order to see the poster's wealth tier before accepting.

**Order limits:** Each agent can have at most `max_open_orders` (configurable, e.g., 5) active posted orders across all nodes. This prevents order spam.

---

## 6. Fitness Definition (Synchronous Mode)

### The Problem

"Ranked by credits" is ambiguous. Final balance? Total earnings? Balance plus commodity value?

### Proposed Solution: Final Net Worth

Fitness = **credits held at end of episode + liquidation value of all commodities.**

Liquidation value is calculated by selling each commodity at the current NPC buy price at the agent's current node (or the average NPC price across all nodes if we want location-independence). This means both credits and commodities count, but commodities are valued at their "floor" price rather than some hypothetical market value.

**Rationale:**
- Pure credit balance penalizes agents who invested in commodities (inventory is strategically valuable but wouldn't be counted). 
- Total lifetime earnings rewards churn over accumulation (an agent that earns and spends 1000 credits scores higher than one that carefully saves 500).
- Net worth (credits + commodity value) rewards the combination of earning and smart resource management.

**Dead agents:** Agents that died during the episode receive a fitness of 0 regardless of their peak wealth. Survival is a prerequisite for fitness.

**Tiebreaker:** If two agents have equal net worth, the one that survived more ticks ranks higher.

---

## 7. Population Management (Asynchronous Mode)

### The Problem

In asynchronous mode, agents die and spawn continuously. Need rules for target population, mass die-off handling, and spawn rates.

### Proposed Solution

**Target population:** A configurable constant (e.g., 20 agents). The system attempts to maintain this count.

**Spawn trigger:** Whenever the living population drops below target, a replacement is queued. Replacements spawn at the start of the next tick's SPAWN phase.

**Spawn rate cap:** At most `max_spawns_per_tick` (e.g., 3) new agents per tick, even if many died simultaneously. This prevents mass die-offs from instantly flooding the world with newborns, and creates a brief period of reduced population that affects the economy.

**Mass die-off recovery:** If a catastrophic event kills most of the population, the world enters a "recovery period" where the spawn rate cap applies and the economy naturally readjusts (NPC budgets accumulate, resources regenerate) before the population is fully replenished. This is a feature, not a bug — it creates punctuated dynamics.

**Parent selection for spawns:** When a new agent needs to be spawned, select a parent via tournament selection from the living population:
- Pick `k` random living agents (tournament size, e.g., k=3)
- The one with the highest current credit balance becomes the parent
- New agent inherits parent's LoRA (with mutation) and seed prompt (with optional mutation)
- New agent gets a fresh ID, spawns at the spawn node, receives starting endowment from treasury

**Minimum population floor:** If the population drops below a critical minimum (e.g., 5), temporarily suspend survival tax for all agents until population recovers. This prevents extinction spirals where too few agents means no trade partners, which means no income, which means more death.

---

## Summary: How Credits Flow in Fixed Supply

```
                    ┌──────────────────────────────────────┐
                    │          WORLD TREASURY               │
                    │   (initial pool of all credits)       │
                    └──┬───────────┬──────────────┬────────┘
                       │           │              │
              ┌────────▼──┐  ┌────▼─────┐  ┌─────▼──────┐
              │  Starting  │  │   NPC    │  │   Death    │
              │ Endowment │  │ Node     │  │  Estate    │
              │ (on spawn)│  │ Budgets  │  │ (unclaimed │
              │           │  │          │  │  portion)  │
              └────┬──────┘  └────┬─────┘  └────────────┘
                   │              │              ▲
                   ▼              ▼              │
              ┌────────────────────────────┐    │
              │      AGENT BALANCES        │    │
              │                            │────┘
              │  earn: sell to NPCs        │  (death)
              │  earn: P2P trades          │
              │  spend: survival tax ──────│───► Treasury
              │  spend: P2P trades         │
              │  spend: buy from NPCs      │
              └────────────────────────────┘
```

Total credits in system = Treasury + All NPC budgets + All agent balances = CONSTANT
