# EvoMarket: Future Work and Ideas Parking Lot

This document captures ideas, extensions, and research directions that are out of scope for the initial implementation but worth revisiting as the project matures.

---

## Game Complexity Extensions

### Crafting System
Add recipes that combine commodities into higher-value goods (e.g., Iron + Wood = Tools, Tools + Stone = Machinery). Crafting creates a production economy on top of the trading economy and introduces comparative advantage — agents near iron and wood can specialize in tool production. Start with a flat recipe list before considering dependency trees.

### Environmental Events
Periodic disruptions to the economic landscape: resource booms (a node temporarily produces 10x), droughts (a region's spawn rates collapse), new node discovery (graph expansion), or resource migration (spawn distributions shift). These create non-stationary fitness landscapes that reward adaptability over static optimization.

### Agent Specialization Roles
Formalized roles with unique abilities: Miners (harvest bonus), Merchants (can see orders at adjacent nodes), Scouts (can inspect agents without using an action), Bankers (can issue loans). Roles could be assigned at spawn or chosen by the agent. This adds strategic depth but significantly complicates balance.

### Long-Distance Communication
Allow agents to send messages to non-local agents at a credit cost. This enables remote deal-making and information brokering but reduces the strategic importance of physical location.

### Agent-to-Agent Hostile Actions
Allow agents to steal from or sabotage others (at a cost/risk). This creates predator-prey dynamics and security considerations. Combined with the will system, it creates assassination incentives. Handle with care — this can easily degenerate the economy if not balanced.

### Contractual Agreements
Formalized contracts that the game engine enforces (e.g., "I will deliver 5 Iron to you in 10 ticks, you pay me 20 Credits now"). Breach results in automatic penalties. This enables futures trading, insurance, and more sophisticated financial instruments.

### Information Markets
Agents can sell information (e.g., "Node 7 has 15 Iron stockpiled" or "Agent X has 200 Credits"). The game doesn't verify truthfulness, so information quality becomes reputation-dependent.

---

## Evolutionary Mechanics Extensions

### LoRA Architecture Search
Evolve not just LoRA weights but also the adapter architecture: which layers to apply LoRA to, what rank to use per layer, alpha values. This is a higher-level search over the structure of the genotype itself.

### Seed Prompt Evolution
The seed prompt that agents receive at birth is itself a heritable trait. Evolve seed prompts alongside LoRA weights — offspring inherit a (possibly mutated) version of their parent's seed prompt. This creates two interacting channels of inheritance: the weights (which shape low-level reasoning patterns) and the seed prompt (which shapes high-level strategy and self-concept). Mutations to the seed prompt could be LLM-generated rewrites rather than random character perturbations. This is a form of memetic evolution layered on top of genetic evolution.

### Prompt Document Analysis
The self-prompting mechanism produces a rich artifact — each agent's accumulated prompt document at time of death is a record of its evolving strategy. Analyze these across generations: do successful agents develop similar note-taking patterns? Do evolved populations produce agents with qualitatively different prompt documents than base model populations? The prompt document is essentially the agent's "culture" — heritable through seed prompts, modifiable during a lifetime.

### MAP-Elites for Behavioral Diversity
Instead of pure fitness maximization, use MAP-Elites to maintain a grid of diverse high-performing strategies across behavioral dimensions (e.g., trade frequency vs. movement frequency, cooperation vs. competition). This prevents premature convergence and produces a richer understanding of the strategy space.

### Co-evolutionary Arms Races
Track whether the population exhibits co-evolutionary dynamics: do strategies cycle (rock-paper-scissors), converge (one dominant strategy), or diversify (stable ecosystem of specialists)? This is an interesting research question independent of whether evolution "improves" agents.

### Cross-Model Evolution
Run evolution across different base models (e.g., evolve LoRA for both a 7B and a 70B model in the same population). Compare whether the evolutionary trajectories differ by model scale. Do larger models find different strategies? Do LoRA adaptations transfer across model sizes?

### Multi-Objective Evolution
Replace the single fitness scalar with a Pareto front across multiple objectives: wealth, survival time, trade network centrality, information accuracy. Use NSGA-II or similar multi-objective evolutionary algorithms. This produces a frontier of non-dominated strategies rather than a single optimum.

### Lamarckian Evolution
After an agent plays the game, fine-tune its LoRA on its own successful trajectories using standard gradient methods, then use the fine-tuned LoRA as the basis for reproduction. This combines evolutionary exploration with gradient-based local refinement — a Lamarckian/Baldwinian hybrid.

---

## Minecraft Integration (Stretch Goal)

### Architecture
Use mineflayer (JavaScript) or a Python equivalent to create a bot client that translates between Minecraft game state and text descriptions. The bot handles low-level actions (pathfinding, block placement, inventory management) while the LLM handles high-level strategy.

### MCP Interface
Expose Minecraft capabilities as MCP tools: `mine_block`, `craft_item`, `move_to`, `trade_with_player`, `send_chat`, `check_inventory`, `look_around`. The LLM receives text descriptions of the visual scene and available actions.

### Economy Mod
Use server-side economy plugins (Vault, Essentials) to create a currency system, chest shops, and trading infrastructure. This provides the economic layer needed for the fitness function.

### Challenges
- Bot development is substantial engineering work
- Minecraft's action space is vastly larger than the text game
- Real-time vs turn-based creates timing pressure
- Visual scene description is lossy and potentially misleading
- Pathfinding and low-level motor control shouldn't be part of what we're evaluating

### Why It's Worth It
- Massive existing community interest
- Rich, well-understood economy dynamics
- Visually compelling demonstrations
- Tests spatial reasoning and long-horizon planning in ways the text game can't

---

## Research Questions

### Does evolution find qualitatively different solutions than fine-tuning?
Compare evolved LoRAs against LoRAs fine-tuned with standard RLHF/DPO on trajectories from the game. Do they produce different behavioral strategies? Different failure modes?

### Does the persistent world create Red Queen dynamics?
In a world shaped by previous generations, does the population continuously adapt (Red Queen hypothesis) or reach stable equilibria? How does this differ between synchronous and asynchronous modes?

### Can evolved economic strategies transfer to real-world tasks?
If agents evolve sophisticated negotiation, planning, or resource management strategies, do those capabilities generalize outside the game environment? Test evolved LoRAs on unrelated benchmarks to check for capability transfer.

### What is the minimum model size for meaningful economic behavior?
Run the same game with models from 1B to 70B+ to find the capability threshold where coherent economic strategy emerges. This has implications for understanding what scale of model is needed for "economic reasoning."

### Mechanistic interpretability of evolved adaptations
Use linear probes and activation analysis to understand what representations change in evolved vs base models. Can we identify "economic reasoning circuits" that evolution strengthens? This connects directly to the broader mechanistic interpretability research program.

### Emergent communication protocols
Do agents develop consistent negotiation patterns, pricing conventions, or signaling systems? How do these differ between evolved and non-evolved populations? Is there evidence of emergent language or conventions beyond what the base model already has?

---

## Infrastructure Ideas

### Experiment Management
Build a dashboard for tracking evolutionary runs: fitness curves, population diversity, economic metrics, genealogy trees. Consider integration with W&B or similar experiment tracking tools.

### Replay System
Record full game state at every tick so that interesting episodes can be replayed and analyzed. Store agent prompts and responses for post-hoc analysis of decision-making.

### Distributed Execution
For large population sizes, distribute agent inference across multiple GPU nodes. The game server is lightweight — the bottleneck is LLM inference. Consider using vLLM's batching capabilities to serve multiple agents from the same base model with different LoRA adapters.

### Community / Open Science
Consider open-sourcing the game server and evolutionary framework. The platform could be used by others to study agent economics, multi-agent coordination, or evolutionary ML. A public leaderboard of evolved strategies could drive community engagement.
