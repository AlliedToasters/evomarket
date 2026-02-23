## ADDED Requirements

### Requirement: NPC budget replenishment
The system SHALL provide a `replenish_npc_budgets(world: WorldState) -> ReplenishResult` function that distributes credits from the treasury to NPC node budgets. The function SHALL respect `treasury_min_reserve` — never reducing the treasury below this threshold. The function SHALL use `transfer_credits()` for all credit movements.

#### Scenario: Equal distribution
- **WHEN** `npc_budget_distribution` is `"equal"` and the treasury has sufficient credits
- **THEN** each NPC node receives an equal share of `npc_budget_replenish_rate` millicredits (total per tick, split across nodes), and the treasury decreases by the total distributed

#### Scenario: Treasury below minimum reserve
- **WHEN** the treasury balance minus `treasury_min_reserve` is less than the requested replenishment amount
- **THEN** only the available amount above the reserve is distributed, and the treasury does not drop below `treasury_min_reserve`

#### Scenario: Treasury at or below minimum reserve
- **WHEN** the treasury balance is at or below `treasury_min_reserve`
- **THEN** no replenishment occurs and the result shows 0 credits distributed

#### Scenario: Invariant preserved after replenishment
- **WHEN** `replenish_npc_budgets()` completes
- **THEN** `world.verify_invariant()` passes

### Requirement: Replenishment result type
The system SHALL define a `ReplenishResult` dataclass with fields: `total_distributed: Millicredits`, `per_node: dict[str, Millicredits]` (node_id → amount received), and `treasury_remaining: Millicredits`.

#### Scenario: Result reflects actual distribution
- **WHEN** replenishment distributes credits to 4 nodes
- **THEN** `total_distributed` equals the sum of all values in `per_node`, and `treasury_remaining` equals the treasury balance after distribution

### Requirement: NPC stockpile decay
The system SHALL provide a `decay_npc_stockpiles(world: WorldState) -> None` function that reduces each NPC node's stockpile by a fraction equal to `config.npc_stockpile_decay_rate` per tick. Stockpile values SHALL be clamped to a minimum of 0 (no negative stockpiles). Decay uses integer truncation: `new_stockpile = stockpile - (stockpile * decay_rate)` rounded down to the nearest integer.

#### Scenario: Standard decay
- **WHEN** a node has NPC stockpile of 20 for IRON and decay rate is 0.1
- **THEN** after decay, the stockpile becomes `20 - int(20 * 0.1) = 18`

#### Scenario: Small stockpile decay to zero
- **WHEN** a node has NPC stockpile of 1 and decay rate is 0.1
- **THEN** after decay, the stockpile becomes `1 - int(1 * 0.1) = 1` (int(0.1) = 0, no change). A stockpile of 1 requires a higher decay rate or multiple ticks to reach 0.

#### Scenario: Zero stockpile unchanged
- **WHEN** a node has NPC stockpile of 0
- **THEN** after decay, the stockpile remains 0

#### Scenario: Prices recover after decay
- **WHEN** a node's NPC stockpile decays from 25 to 22
- **THEN** `get_npc_price()` returns a higher price than before the decay

### Requirement: Tax collection
The system SHALL provide a `collect_tax(world: WorldState, agent_id: str, amount: Millicredits) -> TaxResult` function that transfers credits from an agent to the treasury. If the agent has fewer credits than the requested amount, the function SHALL collect whatever the agent has (balance goes to 0). The function SHALL use `transfer_credits()` for credit movements.

#### Scenario: Agent has sufficient credits
- **WHEN** an agent with 5000mc balance is taxed 1000mc
- **THEN** agent balance becomes 4000mc, treasury increases by 1000mc, and `paid_full` is True

#### Scenario: Agent has insufficient credits
- **WHEN** an agent with 500mc balance is taxed 1000mc
- **THEN** agent balance becomes 0mc, treasury increases by 500mc, `amount_collected` is 500mc, and `paid_full` is False

#### Scenario: Agent with zero balance
- **WHEN** an agent with 0mc balance is taxed
- **THEN** no transfer occurs, `amount_collected` is 0, and `paid_full` is False

#### Scenario: Invariant preserved after tax
- **WHEN** `collect_tax()` completes
- **THEN** `world.verify_invariant()` passes

### Requirement: Tax result type
The system SHALL define a `TaxResult` dataclass with fields: `amount_collected: Millicredits` (actual credits taken), `paid_full: bool` (whether the full tax was paid), and `remaining_balance: Millicredits` (agent's balance after tax).

#### Scenario: Full payment result
- **WHEN** an agent pays the full tax amount
- **THEN** `paid_full` is True and `amount_collected` equals the requested tax amount

### Requirement: Spawn funding
The system SHALL provide a `fund_spawn(world: WorldState, amount: Millicredits) -> bool` function that checks whether the treasury can provide a starting endowment. If the treasury has at least `amount` credits, the function SHALL deduct `amount` from the treasury and return True. If the treasury has insufficient credits, the function SHALL return False without modifying any state.

#### Scenario: Treasury has sufficient funds
- **WHEN** `fund_spawn(world, 30_000)` is called and treasury has 100_000mc
- **THEN** treasury decreases to 70_000mc and the function returns True

#### Scenario: Treasury has insufficient funds
- **WHEN** `fund_spawn(world, 30_000)` is called and treasury has 20_000mc
- **THEN** no credits are transferred and the function returns False

#### Scenario: Invariant preserved after spawn funding
- **WHEN** `fund_spawn()` completes (whether successful or not)
- **THEN** `world.verify_invariant()` passes
