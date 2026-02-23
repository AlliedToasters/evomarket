# Proposal: Inheritance System

## Change ID
`inheritance-system`

## Summary
Implement the will system, death resolution, and estate distribution mechanics including the public will document, local share distribution, and treasury return for unclaimed portions.

## Motivation
The inheritance system creates long-term strategic depth: alliance formation, inheritance-based negotiation leverage, and wealth concentration dynamics. It's also the mechanism that returns credits to circulation on agent death, which is critical for the fixed-supply economy.

## What's Changing

### New Files
- `evomarket/engine/inheritance.py` — Will management, death resolution, estate distribution
- `tests/test_inheritance.py`

### Will Management

`update_will(world: WorldState, agent_id: str, distribution: dict[str, float]) -> WillUpdateResult`
- Validate all beneficiary IDs are valid agent IDs (don't need to be alive — will is a document, not a contract)
- Validate all percentages are ≥ 0
- Percentages need NOT sum to 100% — any remainder goes to default distribution
- Percentages MUST NOT exceed 100% total
- Replace agent's current will entirely
- Will is public — stored on the Agent model, readable by any agent

`get_will(world: WorldState, agent_id: str) -> dict[str, float]`
- Returns the agent's current will
- Used by other agents during OBSERVE phase

### Death Resolution

`resolve_death(world: WorldState, agent_id: str) -> DeathResult`

Called during DEATH phase for each agent with balance ≤ 0 after tax. Handles the full estate distribution:

**Step 1: Calculate estate**
- Total credits: agent's remaining balance (may be 0 or slightly negative due to tax)
- Total inventory: all commodities held
- For inventory: liquidate at average NPC prices across all nodes to convert to credit value, OR distribute commodities directly to beneficiaries. **Decision: distribute commodities directly** — this is more interesting strategically and avoids forced liquidation at possibly bad prices.

**Step 2: Execute will**
For each beneficiary in the will (in order):
- If beneficiary is alive: transfer their allocated percentage of credits and each commodity type (rounded down for commodities, exact for credits)
- If beneficiary is dead: their share becomes unclaimed

**Step 3: Distribute unclaimed portion**
The unclaimed portion = everything not successfully transferred to a living beneficiary.
Split according to configuration:
- `death_local_share_pct` → divided equally among all living agents at the same node as the deceased
- `death_treasury_return_pct` → transferred to world treasury
- Commodity items in the unclaimed portion are destroyed (they can't go to treasury). Only credits flow to treasury.

**Step 4: Clean up**
- Mark agent as `alive = False`
- Cancel all posted orders and pending trades (via trading system)
- Clear pending messages (via communication system)
- Agent's will and prompt document are archived for analysis but removed from active state

**DeathResult:**
- `agent_id: str`
- `total_estate_credits: float`
- `total_estate_commodities: dict[CommodityType, int]`
- `will_distributions: list[WillTransfer]` (who got what from the will)
- `unclaimed_credits: float`
- `unclaimed_commodities: dict[CommodityType, int]`
- `local_share_credits: float` (credits distributed to local agents)
- `treasury_return: float`
- `commodities_destroyed: dict[CommodityType, int]`

**WillTransfer:**
- `beneficiary_id: str`
- `credits: float`
- `commodities: dict[CommodityType, int]`
- `will_percentage: float`
- `alive: bool` (whether transfer succeeded)

### Batch Death Resolution

`resolve_deaths(world: WorldState, dead_agent_ids: list[str]) -> list[DeathResult]`

When multiple agents die in the same tick:
- Process deaths in agent_id order (deterministic)
- An agent who is a beneficiary in another dying agent's will can still receive (they're processed in order)
- BUT: if agent A's will names agent B, and both die this tick, B's share from A depends on processing order. If A is processed first, B is still alive and receives. If B is processed first, B is dead and A's share to B is unclaimed.
- This is intentional — it creates interesting edge cases without adding complexity.

## Acceptance Criteria
- Wills are public and readable by any agent
- Will percentages must not exceed 100% total
- Will execution only transfers to living beneficiaries
- Unclaimed portions split correctly between local agents and treasury
- Commodity items in unclaimed portions are destroyed (not sent to treasury)
- Death processing order is deterministic
- All death operations preserve the fixed-supply invariant
- Edge case: agent dies with empty inventory and 0 credits → no-op distribution
- Edge case: agent's only beneficiary is dead → everything goes to unclaimed pool
- Edge case: all agents at a node die simultaneously → local share has no recipients, all goes to treasury
- Property-based test: random death sequences with random wills preserve invariant

## Dependencies
- `core-data-models`
- `trading-system` (for order cleanup on death — can use interface/stub)
- `communication-system` (for message cleanup on death — can use interface/stub)

## Estimated Complexity
Medium-high. ~400-500 lines of inheritance code, ~500-600 lines of tests (many edge cases).
