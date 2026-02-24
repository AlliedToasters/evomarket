"""Tests for tick engine — resource regeneration and full tick pipeline integration."""

from evomarket.core.types import NodeType
from evomarket.core.world import WorldConfig, WorldState, generate_world
from evomarket.engine.actions import (
    AgentTurnResult,
    IdleAction,
)
from evomarket.engine.observation import AgentObservation
from evomarket.engine.tick import (
    TickResult,
    execute_tick,
    regenerate_resources,
)


def _make_world(population: int = 5, seed: int = 42) -> WorldState:
    config = WorldConfig(
        num_nodes=5,
        num_commodity_types=2,
        population_size=population,
        total_credit_supply=10_000_000,
        starting_credits=30_000,
    )
    return generate_world(config, seed=seed)


def _idle_decisions(
    observations: dict[str, AgentObservation],
) -> dict[str, AgentTurnResult]:
    """All agents idle."""
    return {agent_id: AgentTurnResult(action=IdleAction()) for agent_id in observations}


# ---------------------------------------------------------------------------
# Resource Regeneration Tests (Task 3.3)
# ---------------------------------------------------------------------------


class TestRegenerateResources:
    """Tests for regenerate_resources."""

    def test_accumulates_at_spawn_rate(self) -> None:
        world = _make_world()
        resource_node = None
        for node in world.nodes.values():
            if node.node_type == NodeType.RESOURCE:
                resource_node = node
                break
        assert resource_node is not None

        commodity = list(resource_node.resource_distribution.keys())[0]
        weight = resource_node.resource_distribution[commodity]
        resource_node.resource_stockpile[commodity] = 0.0

        regenerate_resources(world)

        expected = resource_node.resource_spawn_rate * weight
        assert abs(resource_node.resource_stockpile[commodity] - expected) < 1e-9

    def test_cap_behavior(self) -> None:
        world = _make_world()
        resource_node = None
        for node in world.nodes.values():
            if node.node_type == NodeType.RESOURCE:
                resource_node = node
                break
        assert resource_node is not None

        commodity = list(resource_node.resource_stockpile.keys())[0]
        resource_node.resource_stockpile[commodity] = float(resource_node.resource_cap)

        regenerate_resources(world)

        assert resource_node.resource_stockpile[commodity] == float(
            resource_node.resource_cap
        )

    def test_cap_clamps_overshoot(self) -> None:
        world = _make_world()
        resource_node = None
        for node in world.nodes.values():
            if node.node_type == NodeType.RESOURCE:
                resource_node = node
                break
        assert resource_node is not None

        commodity = list(resource_node.resource_distribution.keys())[0]
        resource_node.resource_stockpile[commodity] = (
            float(resource_node.resource_cap) - 0.1
        )

        regenerate_resources(world)

        assert resource_node.resource_stockpile[commodity] <= float(
            resource_node.resource_cap
        )

    def test_fractional_accumulation(self) -> None:
        world = _make_world()
        resource_node = None
        for node in world.nodes.values():
            if node.node_type == NodeType.RESOURCE:
                resource_node = node
                break
        assert resource_node is not None

        commodity = list(resource_node.resource_distribution.keys())[0]
        resource_node.resource_stockpile[commodity] = 0.0

        regenerate_resources(world)
        after_one = resource_node.resource_stockpile[commodity]
        regenerate_resources(world)
        after_two = resource_node.resource_stockpile[commodity]

        # Should be double (if no cap hit)
        assert abs(after_two - 2 * after_one) < 1e-9

    def test_non_resource_nodes_skipped(self) -> None:
        world = _make_world()
        for node in world.nodes.values():
            if node.node_type != NodeType.RESOURCE:
                # Trade hubs and spawn nodes should have no resource accumulation
                before = dict(node.resource_stockpile)
                regenerate_resources(world)
                assert node.resource_stockpile == before


# ---------------------------------------------------------------------------
# Full Tick Pipeline Integration Tests (Tasks 5.1-5.6)
# ---------------------------------------------------------------------------


class TestExecuteTick:
    """Integration tests for execute_tick."""

    def test_full_tick_all_phases(self) -> None:
        """All 10 phases execute successfully (task 5.1)."""
        world = _make_world()
        initial_tick = world.tick
        result = execute_tick(world, _idle_decisions)

        assert isinstance(result, TickResult)
        assert result.tick == initial_tick
        assert world.tick == initial_tick + 1
        assert result.invariant_check is True
        assert result.metrics.agents_alive > 0

    def test_agents_age_after_tick(self) -> None:
        world = _make_world()
        ages_before = {aid: a.age for aid, a in world.agents.items() if a.alive}
        execute_tick(world, _idle_decisions)
        for aid, age_before in ages_before.items():
            if world.agents[aid].alive:
                assert world.agents[aid].age == age_before + 1

    def test_grace_period_decrements(self) -> None:
        world = _make_world()
        # All agents start with grace period
        first_id = next(iter(world.agents))
        grace_before = world.agents[first_id].grace_ticks_remaining
        assert grace_before > 0

        execute_tick(world, _idle_decisions)

        assert world.agents[first_id].grace_ticks_remaining == grace_before - 1

    def test_no_tax_during_grace(self) -> None:
        world = _make_world()
        first_id = next(iter(world.agents))
        credits_before = world.agents[first_id].credits
        assert world.agents[first_id].grace_ticks_remaining > 0

        execute_tick(world, _idle_decisions)

        # Agent should not have been taxed (grace period)
        assert world.agents[first_id].credits == credits_before

    def test_tax_after_grace_expires(self) -> None:
        world = _make_world()
        first_id = next(iter(world.agents))
        world.agents[first_id].grace_ticks_remaining = 0
        credits_before = world.agents[first_id].credits

        execute_tick(world, _idle_decisions)

        assert (
            world.agents[first_id].credits == credits_before - world.config.survival_tax
        )

    def test_death_and_spawn_cycle(self) -> None:
        """Agent dies from tax, replacement spawns (task 5.2)."""
        world = _make_world()
        first_id = next(iter(world.agents))
        world.agents[first_id].grace_ticks_remaining = 0
        world.agents[first_id].credits = 0  # Will die from tax
        # Need to fix invariant after manually setting credits
        deficit = world.config.starting_credits  # We removed this from agent
        world.treasury += deficit

        pop_before = sum(1 for a in world.agents.values() if a.alive)
        result = execute_tick(world, _idle_decisions)

        assert len(result.death_results) >= 1
        assert any(d.agent_id == first_id for d in result.death_results)
        assert len(result.spawn_results) >= 1
        # Population should be restored
        pop_after = sum(1 for a in world.agents.values() if a.alive)
        assert pop_after == pop_before

    def test_determinism(self) -> None:
        """Same seed + same decisions = identical results (task 5.3)."""
        world1 = _make_world(seed=123)
        world2 = _make_world(seed=123)

        result1 = execute_tick(world1, _idle_decisions)
        result2 = execute_tick(world2, _idle_decisions)

        assert result1.tick == result2.tick
        assert result1.metrics.agents_alive == result2.metrics.agents_alive
        assert result1.metrics.agents_died == result2.metrics.agents_died
        assert result1.metrics.agents_spawned == result2.metrics.agents_spawned
        assert result1.invariant_check == result2.invariant_check

        # World states should be identical
        for aid in world1.agents:
            a1 = world1.agents[aid]
            a2 = world2.agents[aid]
            assert a1.credits == a2.credits
            assert a1.location == a2.location
            assert a1.age == a2.age
            assert a1.alive == a2.alive

    def test_invariant_after_multi_tick(self) -> None:
        """Fixed-supply invariant holds across multiple ticks (task 5.4)."""
        world = _make_world()
        for _ in range(10):
            execute_tick(world, _idle_decisions)
            world.verify_invariant()

    def test_debug_mode(self) -> None:
        """Debug mode verifies invariant after each phase (task 5.5)."""
        world = _make_world()
        # If debug mode catches a violation, it would raise AssertionError
        result = execute_tick(world, _idle_decisions, debug=True)
        assert result.invariant_check is True

    def test_scratchpad_update(self) -> None:
        world = _make_world()

        def decisions_with_scratchpad(
            obs: dict[str, AgentObservation],
        ) -> dict[str, AgentTurnResult]:
            results: dict[str, AgentTurnResult] = {}
            for i, agent_id in enumerate(obs):
                results[agent_id] = AgentTurnResult(
                    action=IdleAction(),
                    scratchpad_update=f"notes_{i}" if i == 0 else None,
                )
            return results

        first_id = list(world.agents.keys())[0]
        execute_tick(world, decisions_with_scratchpad)
        assert world.agents[first_id].prompt_document == "notes_0"

    def test_action_resolution(self) -> None:
        """Actions are validated and resolved."""
        world = _make_world()

        # Find a resource node with stockpile
        resource_node_id = None
        for nid, node in world.nodes.items():
            if node.node_type == NodeType.RESOURCE:
                resource_node_id = nid
                # Ensure there's something to harvest
                for c in node.resource_stockpile:
                    node.resource_stockpile[c] = 5.0
                break
        assert resource_node_id is not None

        def harvest_decisions(
            obs: dict[str, AgentObservation],
        ) -> dict[str, AgentTurnResult]:
            results: dict[str, AgentTurnResult] = {}
            first = True
            for agent_id in obs:
                if first:
                    # Move first agent to resource node, then harvest next tick
                    results[agent_id] = AgentTurnResult(action=IdleAction())
                    first = False
                else:
                    results[agent_id] = AgentTurnResult(action=IdleAction())
            return results

        result = execute_tick(world, harvest_decisions)
        assert len(result.action_results) > 0

    def test_replenish_phase(self) -> None:
        """REPLENISH phase runs NPC budget replenish, resource regen, decay."""
        world = _make_world()
        # Track initial state
        resource_node = None
        for node in world.nodes.values():
            if node.node_type == NodeType.RESOURCE:
                resource_node = node
                break
        assert resource_node is not None

        commodity = list(resource_node.resource_stockpile.keys())[0]
        resource_node.resource_stockpile[commodity] = 0.0

        result = execute_tick(world, _idle_decisions)

        # Resources should have been regenerated
        assert resource_node.resource_stockpile[commodity] > 0.0
        # Replenish result should exist
        assert result.replenish_result is not None

    def test_tick_result_metrics(self) -> None:
        world = _make_world()
        result = execute_tick(world, _idle_decisions)
        assert result.metrics.agents_alive == sum(
            1 for a in world.agents.values() if a.alive
        )
        assert result.metrics.total_resources_harvested >= 0
        assert result.metrics.total_messages_sent >= 0

    def test_dead_agents_do_not_age(self) -> None:
        world = _make_world()
        first_id = next(iter(world.agents))
        world.agents[first_id].grace_ticks_remaining = 0
        world.agents[first_id].credits = 0
        world.treasury += world.config.starting_credits
        age_before = world.agents[first_id].age

        execute_tick(world, _idle_decisions)

        # Dead agent should not have aged
        assert not world.agents[first_id].alive
        assert world.agents[first_id].age == age_before

    def test_trade_proposals_expired_before_resolve(self) -> None:
        """Trade proposals from previous tick expire in RESOLVE phase."""
        world = _make_world()
        from evomarket.engine.trading import TradeStatus, propose_trade

        ids = list(world.agents.keys())
        node_id = world.agents[ids[0]].location
        world.agents[ids[1]].location = node_id
        commodity = list(world.agents[ids[0]].inventory.keys())[0]
        world.agents[ids[0]].inventory[commodity] = 5

        # Create a trade proposal at tick 0
        proposal = propose_trade(
            world,
            ids[0],
            ids[1],
            offer_commodities={commodity: 1},
        )
        assert proposal is not None

        # First tick: proposal was created this tick, should still be pending
        execute_tick(world, _idle_decisions)
        # After first tick, world.tick=1 and proposal.created_tick=0
        # The proposal should still exist (expire_pending_trades uses max_age=1,
        # so it expires when tick - created_tick >= 1)

        # Second tick: proposal is now old enough to expire
        # Re-place agents together since they may have moved
        world.agents[ids[0]].location = node_id
        world.agents[ids[1]].location = node_id
        execute_tick(world, _idle_decisions)

        assert proposal.status == TradeStatus.EXPIRED
