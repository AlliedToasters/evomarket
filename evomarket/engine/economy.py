"""NPC economy operations — transactions, treasury management, tax, and spawn funding."""

from __future__ import annotations

from dataclasses import dataclass

from evomarket.core.types import CommodityType, Millicredits
from evomarket.core.world import WorldState


@dataclass(frozen=True)
class NpcTransactionResult:
    """Result of an NPC buy transaction."""

    units_sold: int
    total_credits_received: Millicredits
    price_per_unit: list[Millicredits]
    remaining_budget: Millicredits


@dataclass(frozen=True)
class ReplenishResult:
    """Result of NPC budget replenishment from treasury."""

    total_distributed: Millicredits
    per_node: dict[str, Millicredits]
    treasury_remaining: Millicredits


@dataclass(frozen=True)
class TaxResult:
    """Result of tax collection from an agent."""

    amount_collected: Millicredits
    paid_full: bool
    remaining_balance: Millicredits


def process_npc_sell(
    world: WorldState,
    agent_id: str,
    commodity: CommodityType,
    quantity: int,
) -> NpcTransactionResult:
    """Process an agent selling commodities to the NPC at their current node.

    Price is calculated iteratively per unit — each unit sold increases the NPC
    stockpile before the next unit's price is computed.
    """
    agent = world.agents[agent_id]
    node = world.nodes[agent.location]

    # Commodity not bought at this node
    if commodity not in node.npc_buys:
        return NpcTransactionResult(
            units_sold=0,
            total_credits_received=0,
            price_per_unit=[],
            remaining_budget=node.npc_budget,
        )

    # Cap at agent's actual inventory
    available = agent.inventory.get(commodity, 0)
    units_to_sell = min(quantity, available)

    prices: list[Millicredits] = []
    total_paid: Millicredits = 0

    for _ in range(units_to_sell):
        price = world.get_npc_price(agent.location, commodity)
        if price == 0:
            break
        # Check if NPC budget can cover this unit
        if node.npc_budget < price:
            break

        # Transfer credits from NPC budget to agent
        world.transfer_credits(agent.location, agent_id, price)
        # Update NPC stockpile
        node.npc_stockpile[commodity] = node.npc_stockpile.get(commodity, 0) + 1
        # Remove commodity from agent inventory
        agent.inventory[commodity] -= 1

        prices.append(price)
        total_paid += price

    return NpcTransactionResult(
        units_sold=len(prices),
        total_credits_received=total_paid,
        price_per_unit=prices,
        remaining_budget=node.npc_budget,
    )


def get_npc_prices(
    world: WorldState, node_id: str
) -> dict[CommodityType, Millicredits]:
    """Return current NPC buy prices for all commodities at a node.

    Commodities not bought at the node are omitted.
    """
    node = world.nodes[node_id]
    return {
        commodity: world.get_npc_price(node_id, commodity)
        for commodity in node.npc_buys
    }


def replenish_npc_budgets(world: WorldState) -> ReplenishResult:
    """Distribute credits from treasury to NPC node budgets.

    Respects treasury_min_reserve — never reduces treasury below this threshold.
    Currently only supports "equal" distribution.
    """
    reserve = world.config.treasury_min_reserve
    available = max(0, world.treasury - reserve)
    replenish_total = min(world.config.npc_budget_replenish_rate, available)

    npc_node_ids = [nid for nid, n in world.nodes.items() if n.npc_buys]
    per_node: dict[str, Millicredits] = {}

    if replenish_total == 0 or not npc_node_ids:
        return ReplenishResult(
            total_distributed=0,
            per_node={},
            treasury_remaining=world.treasury,
        )

    # Equal distribution with remainder going to first nodes
    per_node_amount = replenish_total // len(npc_node_ids)
    remainder = replenish_total - per_node_amount * len(npc_node_ids)

    total_distributed: Millicredits = 0
    for i, nid in enumerate(npc_node_ids):
        amount = per_node_amount + (1 if i < remainder else 0)
        if amount > 0:
            world.transfer_credits("treasury", nid, amount)
            per_node[nid] = amount
            total_distributed += amount

    return ReplenishResult(
        total_distributed=total_distributed,
        per_node=per_node,
        treasury_remaining=world.treasury,
    )


def decay_npc_stockpiles(world: WorldState) -> None:
    """Decay NPC stockpiles by the configured rate. Uses integer truncation."""
    rate = world.config.npc_stockpile_decay_rate
    for node in world.nodes.values():
        for commodity in list(node.npc_stockpile.keys()):
            stockpile = node.npc_stockpile[commodity]
            decay_amount = int(stockpile * rate)
            node.npc_stockpile[commodity] = max(0, stockpile - decay_amount)


def collect_tax(world: WorldState, agent_id: str, amount: Millicredits) -> TaxResult:
    """Collect survival tax from an agent. Takes whatever the agent has if insufficient."""
    agent = world.agents[agent_id]
    actual = min(amount, agent.credits)

    if actual > 0:
        world.transfer_credits(agent_id, "treasury", actual)

    return TaxResult(
        amount_collected=actual,
        paid_full=actual >= amount,
        remaining_balance=agent.credits,
    )


def fund_spawn(world: WorldState, amount: Millicredits) -> bool:
    """Check if treasury can fund a spawn and deduct if so.

    Returns True if funded, False if treasury has insufficient credits.
    The caller MUST create an agent with credits=amount to restore the invariant.
    """
    if world.treasury < amount:
        return False
    # Direct mutation: credits are "in transit" until caller creates the agent.
    # The invariant will be temporarily violated until the agent is added.
    world.treasury -= amount
    return True
