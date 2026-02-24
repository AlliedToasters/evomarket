"""Tests for inheritance: will management, death resolution, batch deaths, invariant."""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from evomarket.core.types import CommodityType, Millicredits
from evomarket.core.world import WorldConfig, WorldState, generate_world
from evomarket.engine.inheritance import (
    get_will,
    resolve_death,
    resolve_deaths,
    update_will,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

COMMODITIES = [CommodityType.IRON, CommodityType.WOOD]


def _make_world(
    num_agents: int = 3,
    starting_credits: Millicredits = 30_000,
    seed: int = 42,
) -> WorldState:
    """Create a small world for inheritance tests."""
    config = WorldConfig(
        num_nodes=5,
        num_commodity_types=2,
        population_size=num_agents,
        total_credit_supply=10_000_000,
        starting_credits=starting_credits,
    )
    return generate_world(config, seed=seed)


@pytest.fixture
def world() -> WorldState:
    return _make_world()


def _agent_ids(world: WorldState) -> list[str]:
    return sorted(world.agents.keys())


# ---------------------------------------------------------------------------
# 5. Tests — Will Management
# ---------------------------------------------------------------------------


class TestWillUpdate:
    def test_valid_update_replaces_existing(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b, c = ids[0], ids[1], ids[2]

        # Set initial will
        result = update_will(world, a, {b: 0.5})
        assert result.success
        assert world.agents[a].will == {b: 0.5}

        # Replace with new will
        result = update_will(world, a, {c: 0.8})
        assert result.success
        assert world.agents[a].will == {c: 0.8}
        assert b not in world.agents[a].will

    def test_rejection_percentages_exceed_1(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b, c = ids[0], ids[1], ids[2]
        original_will = dict(world.agents[a].will)

        result = update_will(world, a, {b: 0.6, c: 0.5})
        assert not result.success
        assert result.error is not None
        assert world.agents[a].will == original_will

    def test_rejection_negative_percentage(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b = ids[0], ids[1]
        original_will = dict(world.agents[a].will)

        result = update_will(world, a, {b: -0.1})
        assert not result.success
        assert result.error is not None
        assert world.agents[a].will == original_will

    def test_rejection_nonexistent_beneficiary(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a = ids[0]
        original_will = dict(world.agents[a].will)

        result = update_will(world, a, {"nonexistent_agent": 0.5})
        assert not result.success
        assert "not a valid agent ID" in (result.error or "")
        assert world.agents[a].will == original_will

    def test_accepts_dead_agent_as_beneficiary(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b = ids[0], ids[1]
        world.agents[b].alive = False

        result = update_will(world, a, {b: 0.5})
        assert result.success
        assert world.agents[a].will == {b: 0.5}

    def test_get_will_returns_current(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b = ids[0], ids[1]
        update_will(world, a, {b: 0.7})

        will = get_will(world, a)
        assert will == {b: 0.7}
        # Returned dict is a copy
        will["extra"] = 0.1
        assert "extra" not in world.agents[a].will


# ---------------------------------------------------------------------------
# 6. Tests — Death Resolution
# ---------------------------------------------------------------------------


class TestDeathResolutionSingle:
    def test_full_transfer_single_beneficiary(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b = ids[0], ids[1]

        # Give agent A some inventory
        world.agents[a].inventory[CommodityType.IRON] = 4
        update_will(world, a, {b: 1.0})

        before_b_credits = world.agents[b].credits
        before_b_iron = world.agents[b].inventory[CommodityType.IRON]
        estate_credits = world.agents[a].credits

        result = resolve_death(world, a)

        assert result.agent_id == a
        assert result.total_estate_credits == estate_credits
        assert result.total_estate_commodities[CommodityType.IRON] == 4
        assert world.agents[b].credits == before_b_credits + estate_credits
        assert world.agents[b].inventory[CommodityType.IRON] == before_b_iron + 4
        assert result.unclaimed_credits == 0
        assert not world.agents[a].alive
        world.verify_invariant()

    def test_multiple_beneficiaries_floor_division(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b, c = ids[0], ids[1], ids[2]

        world.agents[a].inventory[CommodityType.IRON] = 5
        update_will(world, a, {b: 0.5, c: 0.3})

        estate_credits = world.agents[a].credits  # 30000
        before_b = world.agents[b].credits
        before_c = world.agents[c].credits

        result = resolve_death(world, a)

        # Will shares: floor(30000 * 0.5) = 15000, floor(30000 * 0.3) = 9000
        b_will = int(estate_credits * 0.5)
        c_will = int(estate_credits * 0.3)
        unclaimed = estate_credits - b_will - c_will  # 6000

        # Unclaimed split: local_share = floor(6000 * 0.5) = 3000, split among b,c
        local_total = int(unclaimed * world.config.death_local_share_pct)
        per_local = local_total // 2  # 1500 each

        assert world.agents[b].credits == before_b + b_will + per_local
        assert world.agents[c].credits == before_c + c_will + per_local

        # Iron: floor(5 * 0.5) = 2, floor(5 * 0.3) = 1
        assert world.agents[b].inventory[CommodityType.IRON] == 2
        assert world.agents[c].inventory[CommodityType.IRON] == 1

        assert result.unclaimed_credits == unclaimed
        world.verify_invariant()

    def test_dead_beneficiary_share_unclaimed(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b, c = ids[0], ids[1], ids[2]

        update_will(world, a, {b: 0.5, c: 0.5})
        world.agents[c].alive = False

        before_b = world.agents[b].credits
        estate_credits = world.agents[a].credits

        result = resolve_death(world, a)

        b_will = int(estate_credits * 0.5)
        c_share = int(estate_credits * 0.5)
        assert result.unclaimed_credits == c_share

        # b also gets local share of unclaimed (only living local agent)
        local_total = int(c_share * world.config.death_local_share_pct)
        assert world.agents[b].credits == before_b + b_will + local_total

        # Check WillTransfer records
        c_transfer = next(t for t in result.will_distributions if t.beneficiary_id == c)
        assert not c_transfer.alive
        world.verify_invariant()

    def test_all_beneficiaries_dead(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b, c = ids[0], ids[1], ids[2]

        update_will(world, a, {b: 0.5, c: 0.5})
        world.agents[b].alive = False
        world.agents[c].alive = False

        estate_credits = world.agents[a].credits
        result = resolve_death(world, a)

        assert result.unclaimed_credits == estate_credits
        world.verify_invariant()

    def test_empty_will(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a = ids[0]

        # Will is already empty by default
        estate_credits = world.agents[a].credits
        result = resolve_death(world, a)

        assert result.unclaimed_credits == estate_credits
        assert len(result.will_distributions) == 0
        world.verify_invariant()

    def test_zero_credits_empty_inventory(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b = ids[0], ids[1]

        # Move all credits to treasury first
        agent_credits = world.agents[a].credits
        world.transfer_credits(a, "treasury", agent_credits)
        # Inventory is already all zeros
        update_will(world, a, {b: 1.0})

        result = resolve_death(world, a)

        assert result.total_estate_credits == 0
        assert all(v == 0 for v in result.total_estate_commodities.values())
        assert result.unclaimed_credits == 0
        assert result.treasury_return == 0
        assert result.local_share_credits == 0
        assert not world.agents[a].alive
        world.verify_invariant()


class TestUnclaimedDistribution:
    def test_local_agents_receive_equal_share(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b, c = ids[0], ids[1], ids[2]

        # All agents at same node (spawn). Empty will → all unclaimed.
        estate_credits = world.agents[a].credits
        before_b = world.agents[b].credits
        before_c = world.agents[c].credits
        before_treasury = world.treasury

        result = resolve_death(world, a)

        local_share_total = int(estate_credits * world.config.death_local_share_pct)
        treasury_share = estate_credits - local_share_total

        # 2 living local agents (b, c — a is deceased)
        per_agent = local_share_total // 2
        remainder = local_share_total - per_agent * 2

        assert world.agents[b].credits == before_b + per_agent
        assert world.agents[c].credits == before_c + per_agent
        assert world.treasury == before_treasury + treasury_share + remainder
        assert result.local_share_credits == per_agent * 2
        assert result.treasury_return == treasury_share + remainder
        world.verify_invariant()

    def test_no_living_agents_at_node(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b, c = ids[0], ids[1], ids[2]

        # Kill all other agents at the same node
        world.agents[b].alive = False
        world.agents[c].alive = False

        estate_credits = world.agents[a].credits
        before_treasury = world.treasury

        result = resolve_death(world, a)

        # All goes to treasury
        assert result.local_share_credits == 0
        assert world.treasury == before_treasury + estate_credits
        world.verify_invariant()

    def test_unclaimed_commodities_destroyed(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a = ids[0]

        world.agents[a].inventory[CommodityType.IRON] = 3
        world.agents[a].inventory[CommodityType.WOOD] = 2

        result = resolve_death(world, a)

        assert result.commodities_destroyed[CommodityType.IRON] == 3
        assert result.commodities_destroyed[CommodityType.WOOD] == 2
        # Agent inventory should be zeroed
        assert world.agents[a].inventory[CommodityType.IRON] == 0
        assert world.agents[a].inventory[CommodityType.WOOD] == 0
        world.verify_invariant()

    def test_cleanup_callbacks_invoked(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a = ids[0]

        cancel_called: list[str] = []
        clear_called: list[str] = []

        def mock_cancel(w: WorldState, aid: str) -> None:
            cancel_called.append(aid)

        def mock_clear(w: WorldState, aid: str) -> None:
            clear_called.append(aid)

        resolve_death(
            world, a, cancel_orders_fn=mock_cancel, clear_messages_fn=mock_clear
        )

        assert cancel_called == [a]
        assert clear_called == [a]
        assert not world.agents[a].alive


# ---------------------------------------------------------------------------
# 7. Tests — Batch Deaths and Invariant
# ---------------------------------------------------------------------------


class TestBatchDeaths:
    def test_earlier_id_processed_first_beneficiary_receives(self) -> None:
        """agent_001's will names agent_002. Both die. agent_001 processed first,
        so agent_002 receives inheritance before their own death is processed."""
        world = _make_world(num_agents=3)
        ids = _agent_ids(world)
        a, b, c = ids[0], ids[1], ids[2]

        # a wills everything to b
        update_will(world, a, {b: 1.0})
        # b wills everything to c
        update_will(world, b, {c: 1.0})

        a_credits = world.agents[a].credits
        b_credits = world.agents[b].credits

        # Both a and b die
        results = resolve_deaths(world, [a, b])

        assert len(results) == 2
        assert results[0].agent_id == a  # processed first
        assert results[1].agent_id == b

        # b should have received a's estate then died,
        # so c should have received b's estate (b_credits + a_credits)
        assert (
            world.agents[c].credits
            == world.config.starting_credits + a_credits + b_credits
        )
        assert not world.agents[a].alive
        assert not world.agents[b].alive
        world.verify_invariant()

    def test_later_id_wills_to_already_dead_earlier_id(self) -> None:
        """agent_002's will names agent_001. Both die. agent_001 processed first
        and marked dead, so agent_002's will to agent_001 is unclaimed."""
        world = _make_world(num_agents=4)
        ids = _agent_ids(world)
        a, b, _c, _d = ids[0], ids[1], ids[2], ids[3]

        # b wills to a (who will already be dead when b is processed)
        update_will(world, b, {a: 1.0})

        results = resolve_deaths(world, [a, b])

        # a processed first, marked dead. b processed next, a is dead → unclaimed.
        b_result = results[1]
        a_transfer = next(
            t for t in b_result.will_distributions if t.beneficiary_id == a
        )
        assert not a_transfer.alive
        assert b_result.unclaimed_credits == b_result.total_estate_credits
        world.verify_invariant()

    def test_all_agents_at_node_die_simultaneously(self) -> None:
        """All agents at a node die. Local share has no recipients → goes to treasury."""
        world = _make_world(num_agents=3)
        ids = _agent_ids(world)

        # All agents are at spawn node
        total_credits = sum(world.agents[aid].credits for aid in ids)
        before_treasury = world.treasury

        resolve_deaths(world, ids)

        # All dead
        for aid in ids:
            assert not world.agents[aid].alive

        # All credits should be in treasury (no living local agents to distribute to)
        assert world.treasury == before_treasury + total_credits
        world.verify_invariant()


class TestInvariantPreservation:
    def test_single_death_preserves_invariant(self, world: WorldState) -> None:
        ids = _agent_ids(world)
        a, b = ids[0], ids[1]
        world.agents[a].inventory[CommodityType.IRON] = 5
        update_will(world, a, {b: 0.6})

        resolve_death(world, a)
        world.verify_invariant()

    def test_batch_deaths_preserve_invariant(self) -> None:
        world = _make_world(num_agents=5)
        ids = _agent_ids(world)

        # Set up some wills and inventory
        update_will(world, ids[0], {ids[1]: 0.3, ids[2]: 0.4})
        update_will(world, ids[1], {ids[3]: 1.0})
        world.agents[ids[0]].inventory[CommodityType.IRON] = 10
        world.agents[ids[1]].inventory[CommodityType.WOOD] = 7

        resolve_deaths(world, [ids[0], ids[1], ids[2]])
        world.verify_invariant()

    @given(
        seed=st.integers(min_value=0, max_value=10000),
        num_deaths=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=50, deadline=None)
    def test_random_deaths_preserve_invariant(self, seed: int, num_deaths: int) -> None:
        """Property-based: random death sequences with random wills preserve invariant."""
        rng = random.Random(seed)
        world = _make_world(num_agents=8, seed=seed)
        ids = _agent_ids(world)

        # Assign random inventory
        for aid in ids:
            for c in COMMODITIES:
                world.agents[aid].inventory[c] = rng.randint(0, 10)

        # Assign random wills
        for aid in ids:
            num_beneficiaries = rng.randint(0, 3)
            others = [x for x in ids if x != aid]
            if num_beneficiaries > 0 and others:
                beneficiaries = rng.sample(others, min(num_beneficiaries, len(others)))
                remaining = 1.0
                will: dict[str, float] = {}
                for i, bid in enumerate(beneficiaries):
                    if i == len(beneficiaries) - 1:
                        pct = round(rng.uniform(0, remaining), 2)
                    else:
                        pct = round(rng.uniform(0, remaining / 2), 2)
                    will[bid] = pct
                    remaining -= pct
                update_will(world, aid, will)

        # Kill random subset
        num_to_kill = min(num_deaths, len(ids))
        dead = rng.sample(ids, num_to_kill)

        resolve_deaths(world, dead)
        world.verify_invariant()
