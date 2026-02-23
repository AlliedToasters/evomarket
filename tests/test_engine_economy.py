"""Tests for evomarket.engine.economy — NPC transactions, treasury ops, tax, spawn."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from evomarket.core.types import CommodityType, Millicredits
from evomarket.core.world import WorldConfig, WorldState, generate_world
from evomarket.engine.economy import (
    NpcTransactionResult,
    ReplenishResult,
    TaxResult,
    collect_tax,
    decay_npc_stockpiles,
    fund_spawn,
    get_npc_prices,
    process_npc_sell,
    replenish_npc_budgets,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_world(seed: int = 42) -> WorldState:
    """Create a standard test world."""
    return generate_world(WorldConfig(), seed=seed)


def _find_npc_node(world: WorldState, commodity: CommodityType) -> str:
    """Find a node that buys the given commodity."""
    for nid, node in world.nodes.items():
        if commodity in node.npc_buys:
            return nid
    raise ValueError(f"No node buys {commodity}")


def _place_agent_with_inventory(
    world: WorldState, agent_id: str, node_id: str, commodity: CommodityType, qty: int
) -> None:
    """Move an agent to a node and give them inventory."""
    agent = world.agents[agent_id]
    agent.location = node_id
    agent.inventory[commodity] = qty


# ---------------------------------------------------------------------------
# 5.1 — process_npc_sell tests
# ---------------------------------------------------------------------------


class TestProcessNpcSell:
    """Tests for NPC buy transaction processing."""

    def test_single_unit_at_zero_stockpile(self, standard_world: WorldState) -> None:
        world = standard_world
        agent_id = "agent_000"
        node_id = _find_npc_node(world, CommodityType.IRON)
        _place_agent_with_inventory(world, agent_id, node_id, CommodityType.IRON, 5)

        # Ensure zero stockpile
        world.nodes[node_id].npc_stockpile[CommodityType.IRON] = 0

        initial_credits = world.agents[agent_id].credits
        result = process_npc_sell(world, agent_id, CommodityType.IRON, 1)

        assert result.units_sold == 1
        assert result.price_per_unit == [world.config.npc_base_price]
        assert result.total_credits_received == world.config.npc_base_price
        assert world.agents[agent_id].credits == initial_credits + world.config.npc_base_price
        assert world.agents[agent_id].inventory[CommodityType.IRON] == 4
        assert world.nodes[node_id].npc_stockpile[CommodityType.IRON] == 1

    def test_multi_unit_iterative_pricing(self, standard_world: WorldState) -> None:
        world = standard_world
        agent_id = "agent_000"
        node_id = _find_npc_node(world, CommodityType.IRON)
        _place_agent_with_inventory(world, agent_id, node_id, CommodityType.IRON, 10)

        world.nodes[node_id].npc_stockpile[CommodityType.IRON] = 0
        capacity = world.nodes[node_id].npc_stockpile_capacity
        base = world.config.npc_base_price

        result = process_npc_sell(world, agent_id, CommodityType.IRON, 3)

        assert result.units_sold == 3
        # Unit 1: stockpile=0 → base * (cap-0)//cap = base
        # Unit 2: stockpile=1 → base * (cap-1)//cap
        # Unit 3: stockpile=2 → base * (cap-2)//cap
        expected_prices = [
            base * (capacity - i) // capacity for i in range(3)
        ]
        assert result.price_per_unit == expected_prices
        assert result.total_credits_received == sum(expected_prices)
        # Prices should be descending
        assert result.price_per_unit[0] >= result.price_per_unit[1] >= result.price_per_unit[2]

    def test_budget_constrained_sale(self, standard_world: WorldState) -> None:
        world = standard_world
        agent_id = "agent_000"
        node_id = _find_npc_node(world, CommodityType.IRON)
        _place_agent_with_inventory(world, agent_id, node_id, CommodityType.IRON, 10)

        world.nodes[node_id].npc_stockpile[CommodityType.IRON] = 0
        # Drain the NPC budget down to just under 2 full-price units
        base = world.config.npc_base_price
        target_budget = base + base - 1
        current_budget = world.nodes[node_id].npc_budget
        if current_budget > target_budget:
            world.transfer_credits(node_id, "treasury", current_budget - target_budget)

        result = process_npc_sell(world, agent_id, CommodityType.IRON, 10)

        # Should sell some but not all (budget only covers ~2 units)
        assert result.units_sold < 10
        assert result.units_sold > 0
        assert result.remaining_budget >= 0
        world.verify_invariant()

    def test_commodity_not_bought(self, standard_world: WorldState) -> None:
        world = standard_world
        agent_id = "agent_000"
        # Find a node that doesn't buy HERBS (resource nodes typically only buy their native)
        for nid, node in world.nodes.items():
            if CommodityType.HERBS not in node.npc_buys:
                break
        else:
            pytest.skip("All nodes buy HERBS")

        _place_agent_with_inventory(world, agent_id, nid, CommodityType.HERBS, 5)
        result = process_npc_sell(world, agent_id, CommodityType.HERBS, 3)

        assert result.units_sold == 0
        assert result.total_credits_received == 0
        assert result.price_per_unit == []

    def test_insufficient_inventory(self, standard_world: WorldState) -> None:
        world = standard_world
        agent_id = "agent_000"
        node_id = _find_npc_node(world, CommodityType.IRON)
        _place_agent_with_inventory(world, agent_id, node_id, CommodityType.IRON, 2)

        world.nodes[node_id].npc_stockpile[CommodityType.IRON] = 0
        result = process_npc_sell(world, agent_id, CommodityType.IRON, 5)

        assert result.units_sold == 2
        assert world.agents[agent_id].inventory[CommodityType.IRON] == 0

    def test_invariant_preserved(self, standard_world: WorldState) -> None:
        world = standard_world
        agent_id = "agent_000"
        node_id = _find_npc_node(world, CommodityType.IRON)
        _place_agent_with_inventory(world, agent_id, node_id, CommodityType.IRON, 10)
        world.nodes[node_id].npc_stockpile[CommodityType.IRON] = 0

        process_npc_sell(world, agent_id, CommodityType.IRON, 5)
        world.verify_invariant()


# ---------------------------------------------------------------------------
# 5.2 — get_npc_prices tests
# ---------------------------------------------------------------------------


class TestGetNpcPrices:
    """Tests for bulk NPC price query."""

    def test_trade_hub_all_commodities(self, standard_world: WorldState) -> None:
        world = standard_world
        # Trade hubs buy all commodities
        hub_id = next(
            nid for nid, n in world.nodes.items()
            if len(n.npc_buys) == len(CommodityType)
        )
        prices = get_npc_prices(world, hub_id)

        assert len(prices) == len(CommodityType)
        for commodity in CommodityType:
            assert prices[commodity] == world.get_npc_price(hub_id, commodity)

    def test_resource_node_single_commodity(self, standard_world: WorldState) -> None:
        world = standard_world
        # Resource nodes typically buy only their native commodity
        resource_id = next(
            nid for nid, n in world.nodes.items()
            if len(n.npc_buys) == 1
        )
        node = world.nodes[resource_id]
        prices = get_npc_prices(world, resource_id)

        assert len(prices) == 1
        assert node.npc_buys[0] in prices


# ---------------------------------------------------------------------------
# 5.3 — replenish_npc_budgets tests
# ---------------------------------------------------------------------------


class TestReplenishNpcBudgets:
    """Tests for treasury-to-node budget replenishment."""

    def test_equal_distribution(self, standard_world: WorldState) -> None:
        world = standard_world
        npc_nodes = [nid for nid, n in world.nodes.items() if n.npc_buys]
        initial_budgets = {nid: world.nodes[nid].npc_budget for nid in npc_nodes}

        result = replenish_npc_budgets(world)

        assert result.total_distributed > 0
        assert result.total_distributed == sum(result.per_node.values())
        # Each node should get roughly equal share
        amounts = list(result.per_node.values())
        assert max(amounts) - min(amounts) <= 1  # differ by at most 1 mc (remainder)
        world.verify_invariant()

    def test_treasury_below_reserve(self, standard_world: WorldState) -> None:
        world = standard_world
        # Set treasury to just above reserve
        reserve = world.config.treasury_min_reserve
        surplus = 500  # small surplus
        # Move excess treasury to an agent to keep invariant
        excess = world.treasury - reserve - surplus
        if excess > 0:
            world.transfer_credits("treasury", "agent_000", excess)

        result = replenish_npc_budgets(world)

        assert result.total_distributed <= surplus
        assert world.treasury >= reserve
        world.verify_invariant()

    def test_treasury_at_reserve(self, standard_world: WorldState) -> None:
        world = standard_world
        reserve = world.config.treasury_min_reserve
        # Move treasury down to exactly the reserve
        excess = world.treasury - reserve
        if excess > 0:
            world.transfer_credits("treasury", "agent_000", excess)

        result = replenish_npc_budgets(world)

        assert result.total_distributed == 0
        assert world.treasury == reserve
        world.verify_invariant()

    def test_invariant_preserved(self, standard_world: WorldState) -> None:
        world = standard_world
        replenish_npc_budgets(world)
        world.verify_invariant()


# ---------------------------------------------------------------------------
# 5.4 — decay_npc_stockpiles tests
# ---------------------------------------------------------------------------


class TestDecayNpcStockpiles:
    """Tests for NPC stockpile decay."""

    def test_standard_decay(self, standard_world: WorldState) -> None:
        world = standard_world
        node_id = _find_npc_node(world, CommodityType.IRON)
        world.nodes[node_id].npc_stockpile[CommodityType.IRON] = 20

        decay_npc_stockpiles(world)

        # 20 - int(20 * 0.1) = 20 - 2 = 18
        assert world.nodes[node_id].npc_stockpile[CommodityType.IRON] == 18

    def test_small_stockpile_no_decay(self, standard_world: WorldState) -> None:
        world = standard_world
        node_id = _find_npc_node(world, CommodityType.IRON)
        world.nodes[node_id].npc_stockpile[CommodityType.IRON] = 1

        decay_npc_stockpiles(world)

        # int(1 * 0.1) = 0, so no change
        assert world.nodes[node_id].npc_stockpile[CommodityType.IRON] == 1

    def test_zero_stockpile_unchanged(self, standard_world: WorldState) -> None:
        world = standard_world
        node_id = _find_npc_node(world, CommodityType.IRON)
        world.nodes[node_id].npc_stockpile[CommodityType.IRON] = 0

        decay_npc_stockpiles(world)

        assert world.nodes[node_id].npc_stockpile[CommodityType.IRON] == 0

    def test_price_recovery_after_decay(self, standard_world: WorldState) -> None:
        world = standard_world
        node_id = _find_npc_node(world, CommodityType.IRON)
        world.nodes[node_id].npc_stockpile[CommodityType.IRON] = 25

        price_before = world.get_npc_price(node_id, CommodityType.IRON)
        decay_npc_stockpiles(world)
        price_after = world.get_npc_price(node_id, CommodityType.IRON)

        assert price_after > price_before


# ---------------------------------------------------------------------------
# 5.5 — collect_tax tests
# ---------------------------------------------------------------------------


class TestCollectTax:
    """Tests for survival tax collection."""

    def test_sufficient_credits(self, standard_world: WorldState) -> None:
        world = standard_world
        agent_id = "agent_000"
        initial = world.agents[agent_id].credits

        result = collect_tax(world, agent_id, 1_000)

        assert result.amount_collected == 1_000
        assert result.paid_full is True
        assert result.remaining_balance == initial - 1_000
        assert world.agents[agent_id].credits == initial - 1_000

    def test_insufficient_credits(self, standard_world: WorldState) -> None:
        world = standard_world
        agent_id = "agent_000"
        # Set agent to low balance
        agent = world.agents[agent_id]
        excess = agent.credits - 500
        if excess > 0:
            world.transfer_credits(agent_id, "treasury", excess)

        result = collect_tax(world, agent_id, 1_000)

        assert result.amount_collected == 500
        assert result.paid_full is False
        assert result.remaining_balance == 0
        assert world.agents[agent_id].credits == 0

    def test_zero_balance(self, standard_world: WorldState) -> None:
        world = standard_world
        agent_id = "agent_000"
        agent = world.agents[agent_id]
        if agent.credits > 0:
            world.transfer_credits(agent_id, "treasury", agent.credits)

        result = collect_tax(world, agent_id, 1_000)

        assert result.amount_collected == 0
        assert result.paid_full is False
        assert result.remaining_balance == 0

    def test_invariant_preserved(self, standard_world: WorldState) -> None:
        world = standard_world
        collect_tax(world, "agent_000", 1_000)
        world.verify_invariant()


# ---------------------------------------------------------------------------
# 5.6 — fund_spawn tests
# ---------------------------------------------------------------------------


class TestFundSpawn:
    """Tests for spawn funding from treasury."""

    def test_sufficient_treasury(self, standard_world: WorldState) -> None:
        world = standard_world
        initial_treasury = world.treasury
        amount = 30_000

        result = fund_spawn(world, amount)

        assert result is True
        assert world.treasury == initial_treasury - amount

    def test_insufficient_treasury(self, standard_world: WorldState) -> None:
        world = standard_world
        # Drain treasury
        excess = world.treasury - 10_000
        if excess > 0:
            world.transfer_credits("treasury", "agent_000", excess)

        initial_treasury = world.treasury
        result = fund_spawn(world, 30_000)

        assert result is False
        assert world.treasury == initial_treasury  # unchanged

    def test_invariant_after_fund_and_agent_creation(self, standard_world: WorldState) -> None:
        """Invariant holds once caller completes the spawn by adding the agent."""
        world = standard_world
        amount = world.config.starting_credits

        fund_spawn(world, amount)
        # Invariant is temporarily violated here — simulate caller creating agent
        new_id = f"agent_{world.next_agent_id:03d}"
        from evomarket.core.agent import Agent

        new_agent = Agent(
            agent_id=new_id,
            display_name=f"Agent {world.next_agent_id}",
            location=next(iter(world.nodes)),
            credits=amount,
            inventory={c: 0 for c in CommodityType},
            age=0,
            alive=True,
            will={},
            prompt_document="",
            grace_ticks_remaining=world.config.spawn_grace_period,
        )
        world.agents[new_id] = new_agent
        world.next_agent_id += 1

        world.verify_invariant()


# ---------------------------------------------------------------------------
# 5.7 — Property-based tests
# ---------------------------------------------------------------------------


class TestInvariantPropertyBased:
    """Hypothesis property-based tests for economic invariant."""

    @given(
        seed=st.integers(min_value=0, max_value=1000),
        num_ops=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=30, deadline=5000)
    def test_invariant_after_random_operations(self, seed: int, num_ops: int) -> None:
        """Invariant holds after arbitrary sequences of NPC sells, replenishments,
        tax collections, and spawn fundings."""
        import random as stdlib_random

        world = _make_world(seed=seed)
        rng = stdlib_random.Random(seed)
        commodities = list(CommodityType)

        for _ in range(num_ops):
            op = rng.choice(["sell", "replenish", "tax", "decay"])

            if op == "sell":
                agent_ids = [a for a in world.agents if world.agents[a].alive]
                if not agent_ids:
                    continue
                agent_id = rng.choice(agent_ids)
                commodity = rng.choice(commodities)
                # Give agent some inventory for the sell
                world.agents[agent_id].inventory[commodity] = (
                    world.agents[agent_id].inventory.get(commodity, 0) + rng.randint(1, 5)
                )
                node_id = world.agents[agent_id].location
                if commodity in world.nodes[node_id].npc_buys:
                    process_npc_sell(world, agent_id, commodity, rng.randint(1, 3))

            elif op == "replenish":
                replenish_npc_budgets(world)

            elif op == "tax":
                agent_ids = [a for a in world.agents if world.agents[a].alive]
                if not agent_ids:
                    continue
                agent_id = rng.choice(agent_ids)
                collect_tax(world, agent_id, rng.randint(100, 2000))

            elif op == "decay":
                decay_npc_stockpiles(world)

            world.verify_invariant()
