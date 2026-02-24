"""Tests for economy: invariant, transfers, NPC pricing, treasury, checkpointing."""

import pytest

from evomarket.core.types import CommodityType
from evomarket.core.world import WorldConfig, WorldState, generate_world


@pytest.fixture
def world() -> WorldState:
    config = WorldConfig(num_nodes=5, num_commodity_types=2, population_size=3)
    return generate_world(config, seed=42)


class TestInvariant:
    def test_holds_after_generation(self, world: WorldState) -> None:
        world.verify_invariant()

    def test_holds_after_transfer(self, world: WorldState) -> None:
        agents = list(world.agents.keys())
        world.transfer_credits(agents[0], agents[1], 1000)
        world.verify_invariant()

    def test_violation_detected(self, world: WorldState) -> None:
        # Directly mutate to break invariant
        first_agent = next(iter(world.agents.values()))
        first_agent.credits += 1
        with pytest.raises(AssertionError, match="invariant violated"):
            world.verify_invariant()


class TestTransferCredits:
    def test_agent_to_agent(self, world: WorldState) -> None:
        agents = list(world.agents.keys())
        a, b = agents[0], agents[1]
        before_a = world.agents[a].credits
        before_b = world.agents[b].credits
        world.transfer_credits(a, b, 10_000)
        assert world.agents[a].credits == before_a - 10_000
        assert world.agents[b].credits == before_b + 10_000

    def test_agent_to_treasury(self, world: WorldState) -> None:
        agent = next(iter(world.agents.keys()))
        before_agent = world.agents[agent].credits
        before_treasury = world.treasury
        world.transfer_credits(agent, "treasury", 5_000)
        assert world.agents[agent].credits == before_agent - 5_000
        assert world.treasury == before_treasury + 5_000

    def test_treasury_to_node(self, world: WorldState) -> None:
        # Find a node with npc_budget
        node_id = None
        for nid, node in world.nodes.items():
            if node.npc_buys:
                node_id = nid
                break
        assert node_id is not None
        before_treasury = world.treasury
        before_budget = world.nodes[node_id].npc_budget
        world.transfer_credits("treasury", node_id, 20_000)
        assert world.treasury == before_treasury - 20_000
        assert world.nodes[node_id].npc_budget == before_budget + 20_000

    def test_node_to_agent(self, world: WorldState) -> None:
        agent = next(iter(world.agents.keys()))
        node_id = None
        for nid, node in world.nodes.items():
            if node.npc_budget > 0:
                node_id = nid
                break
        assert node_id is not None
        before_agent = world.agents[agent].credits
        before_budget = world.nodes[node_id].npc_budget
        amount = min(5_000, before_budget)
        world.transfer_credits(node_id, agent, amount)
        assert world.agents[agent].credits == before_agent + amount
        assert world.nodes[node_id].npc_budget == before_budget - amount

    def test_insufficient_funds(self, world: WorldState) -> None:
        agents = list(world.agents.keys())
        a, b = agents[0], agents[1]
        before_a = world.agents[a].credits
        before_b = world.agents[b].credits
        with pytest.raises(ValueError, match="Insufficient"):
            world.transfer_credits(a, b, before_a + 1)
        # Balances unchanged
        assert world.agents[a].credits == before_a
        assert world.agents[b].credits == before_b

    def test_zero_amount(self, world: WorldState) -> None:
        agents = list(world.agents.keys())
        a, b = agents[0], agents[1]
        before_a = world.agents[a].credits
        before_b = world.agents[b].credits
        world.transfer_credits(a, b, 0)
        assert world.agents[a].credits == before_a
        assert world.agents[b].credits == before_b

    def test_negative_amount_rejected(self, world: WorldState) -> None:
        agents = list(world.agents.keys())
        with pytest.raises(ValueError, match="non-negative"):
            world.transfer_credits(agents[0], agents[1], -100)

    def test_unknown_reservoir(self, world: WorldState) -> None:
        with pytest.raises(KeyError, match="Unknown reservoir"):
            world.transfer_credits("nonexistent", "treasury", 100)


class TestNpcPricing:
    def _get_npc_node(self, world: WorldState) -> tuple[str, CommodityType]:
        """Find a node that buys a commodity and return (node_id, commodity)."""
        for nid, node in world.nodes.items():
            if node.npc_buys:
                return nid, node.npc_buys[0]
        pytest.fail("No NPC node found")

    def test_price_at_zero_stockpile(self, world: WorldState) -> None:
        nid, commodity = self._get_npc_node(world)
        node = world.nodes[nid]
        node.npc_stockpile[commodity] = 0
        price = world.get_npc_price(nid, commodity)
        assert price == node.npc_base_prices[commodity]

    def test_price_at_full_stockpile(self, world: WorldState) -> None:
        nid, commodity = self._get_npc_node(world)
        node = world.nodes[nid]
        node.npc_stockpile[commodity] = node.npc_stockpile_capacity
        price = world.get_npc_price(nid, commodity)
        assert price == 0

    def test_price_at_half_stockpile(self, world: WorldState) -> None:
        nid, commodity = self._get_npc_node(world)
        node = world.nodes[nid]
        node.npc_stockpile[commodity] = node.npc_stockpile_capacity // 2
        price = world.get_npc_price(nid, commodity)
        base = node.npc_base_prices[commodity]
        capacity = node.npc_stockpile_capacity
        stockpile = node.npc_stockpile[commodity]
        expected = base * (capacity - stockpile) // capacity
        assert price == expected

    def test_commodity_not_bought(self, world: WorldState) -> None:
        # Find a node and a commodity it doesn't buy
        for nid, node in world.nodes.items():
            commodities = [
                CommodityType.IRON,
                CommodityType.WOOD,
                CommodityType.STONE,
                CommodityType.HERBS,
            ]
            for c in commodities:
                if c not in node.npc_buys:
                    assert world.get_npc_price(nid, c) == 0
                    return
        pytest.skip("All commodities bought at all nodes")


class TestTreasury:
    def test_treasury_initialized_correctly(self) -> None:
        config = WorldConfig(
            num_nodes=5,
            num_commodity_types=2,
            population_size=3,
            total_credit_supply=10_000_000,
            starting_credits=30_000,
        )
        world = generate_world(config, seed=42)
        agent_credits = sum(a.credits for a in world.agents.values())
        npc_budgets = sum(n.npc_budget for n in world.nodes.values())
        assert (
            world.treasury == config.total_credit_supply - agent_credits - npc_budgets
        )

    def test_treasury_non_negative(self, world: WorldState) -> None:
        assert world.treasury >= 0


class TestAgentsAtNode:
    def test_agents_at_spawn(self, world: WorldState) -> None:
        agents = world.agents_at_node("node_spawn")
        # All agents start at spawn
        assert len(agents) == len(world.agents)

    def test_dead_agents_excluded(self, world: WorldState) -> None:
        first_agent = next(iter(world.agents.values()))
        first_agent.alive = False
        agents = world.agents_at_node(first_agent.location)
        assert first_agent not in agents

    def test_empty_node(self, world: WorldState) -> None:
        # Find a node with no agents
        agent_locations = {a.location for a in world.agents.values()}
        for nid in world.nodes:
            if nid not in agent_locations:
                assert world.agents_at_node(nid) == []
                return


class TestCheckpointing:
    def test_round_trip(self, world: WorldState) -> None:
        # Generate some RNG values before serializing
        world.rng.random()

        data = world.to_json()
        restored = WorldState.from_json(data)

        assert restored.treasury == world.treasury
        assert restored.total_supply == world.total_supply
        assert restored.tick == world.tick
        assert restored.next_agent_id == world.next_agent_id
        assert set(restored.nodes.keys()) == set(world.nodes.keys())
        assert set(restored.agents.keys()) == set(world.agents.keys())

        # RNG state should produce the same next values
        assert restored.rng.random() == world.rng.random()

    def test_invariant_after_round_trip(self, world: WorldState) -> None:
        data = world.to_json()
        restored = WorldState.from_json(data)
        restored.verify_invariant()
