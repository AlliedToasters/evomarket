"""Tests for agent spawning."""

from evomarket.core.types import NodeType
from evomarket.core.world import WorldConfig, generate_world, WorldState
from evomarket.engine.spawning import spawn_agents


def _make_world(population: int = 5, treasury: int | None = None) -> WorldState:
    config = WorldConfig(
        num_nodes=5,
        num_commodity_types=2,
        population_size=population,
        total_credit_supply=10_000_000,
        starting_credits=30_000,
    )
    world = generate_world(config, seed=42)
    if treasury is not None:
        # Adjust treasury to desired value
        diff = treasury - world.treasury
        world.treasury = treasury
        # Absorb diff into total_supply to keep invariant
        world.total_supply += diff
    return world


class TestSpawning:
    """Tests for spawn_agents."""

    def test_no_spawn_at_population_target(self) -> None:
        world = _make_world(population=5)
        results = spawn_agents(world)
        assert results == []

    def test_spawns_to_fill_gap(self) -> None:
        world = _make_world(population=5)
        # Kill one agent
        first_id = next(iter(world.agents))
        world.agents[first_id].alive = False
        results = spawn_agents(world)
        assert len(results) == 1

    def test_spawn_funded_from_treasury(self) -> None:
        world = _make_world(population=5)
        first_id = next(iter(world.agents))
        world.agents[first_id].alive = False
        treasury_before = world.treasury
        spawn_agents(world)
        assert world.treasury == treasury_before - world.config.starting_credits

    def test_spawn_agent_initialized_correctly(self) -> None:
        world = _make_world(population=5)
        first_id = next(iter(world.agents))
        world.agents[first_id].alive = False
        results = spawn_agents(world)
        new_agent = world.agents[results[0].agent_id]
        assert new_agent.alive
        assert new_agent.credits == world.config.starting_credits
        assert new_agent.age == 0
        assert new_agent.grace_ticks_remaining == world.config.spawn_grace_period
        assert all(qty == 0 for qty in new_agent.inventory.values())
        assert new_agent.will == {}
        assert new_agent.prompt_document == ""

    def test_spawn_at_spawn_node(self) -> None:
        world = _make_world(population=5)
        first_id = next(iter(world.agents))
        world.agents[first_id].alive = False
        results = spawn_agents(world)
        spawn_node_ids = [
            n.node_id for n in world.nodes.values() if n.node_type == NodeType.SPAWN
        ]
        assert results[0].location in spawn_node_ids

    def test_deterministic_agent_ids(self) -> None:
        world = _make_world(population=5)
        next_id = world.next_agent_id
        # Kill two agents
        ids = list(world.agents.keys())
        world.agents[ids[0]].alive = False
        world.agents[ids[1]].alive = False
        results = spawn_agents(world)
        assert results[0].agent_id == f"agent_{next_id:03d}"
        assert results[1].agent_id == f"agent_{next_id + 1:03d}"
        assert world.next_agent_id == next_id + 2

    def test_treasury_exhaustion_stops_spawning(self) -> None:
        world = _make_world(population=5)
        # Kill 3 agents
        ids = list(world.agents.keys())
        for aid in ids[:3]:
            world.agents[aid].alive = False
        # Set treasury to only fund 1 spawn
        world.treasury = world.config.starting_credits + 100
        # Adjust total_supply to match
        world.total_supply = (
            sum(a.credits for a in world.agents.values())
            + sum(n.npc_budget for n in world.nodes.values())
            + world.treasury
        )
        results = spawn_agents(world)
        assert len(results) == 1  # Only 1 funded, not 3

    def test_multiple_spawns(self) -> None:
        world = _make_world(population=5)
        ids = list(world.agents.keys())
        for aid in ids[:3]:
            world.agents[aid].alive = False
        results = spawn_agents(world)
        assert len(results) == 3
        # All new agents are alive
        for r in results:
            assert world.agents[r.agent_id].alive

    def test_spawn_result_fields(self) -> None:
        world = _make_world(population=5)
        first_id = next(iter(world.agents))
        world.agents[first_id].alive = False
        results = spawn_agents(world)
        r = results[0]
        assert r.agent_id.startswith("agent_")
        assert r.location in world.nodes
        assert r.starting_credits == world.config.starting_credits
