"""Tests for the trading system: order book, P2P trades, settlement, and history."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from evomarket.core.types import CommodityType, Millicredits
from evomarket.core.world import WorldConfig, WorldState, generate_world
from evomarket.engine.trading import (
    BuySell,
    OrderStatus,
    TradeProposal,
    TradeStatus,
    accept_order,
    accept_trade,
    cancel_all_orders_for_agent,
    cancel_order,
    expire_pending_trades,
    get_trade_history,
    post_order,
    propose_trade,
    reactivate_orders_for_agent,
    reject_trade,
    suspend_orders_for_agent,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def world() -> WorldState:
    """Small world with 2 agents co-located at a trade hub for easy testing."""
    config = WorldConfig(
        num_nodes=5,
        num_commodity_types=2,
        population_size=2,
        total_credit_supply=10_000_000,
        starting_credits=100_000,
        max_open_orders=5,
        max_pending_trades=3,
    )
    w = generate_world(config, seed=42)

    # Move both agents to the same trade hub and give them inventory
    hub_id = next(
        nid for nid, n in w.nodes.items() if n.node_type.value == "TRADE_HUB"
    )
    for agent in w.agents.values():
        agent.location = hub_id
        agent.inventory[CommodityType.IRON] = 10
        agent.inventory[CommodityType.WOOD] = 10

    return w


def _agent_ids(world: WorldState) -> tuple[str, str]:
    """Return the two agent IDs from the test world."""
    ids = sorted(world.agents.keys())
    return ids[0], ids[1]


def _hub_id(world: WorldState) -> str:
    """Return the trade hub ID where agents are located."""
    return next(iter(world.agents.values())).location


# ---------------------------------------------------------------------------
# 6.1 Test post_order
# ---------------------------------------------------------------------------


class TestPostOrder:
    def test_successful_sell_order(self, world: WorldState) -> None:
        a1, _ = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=5,
            price_per_unit=3000,
        )
        assert order is not None
        assert order.status == OrderStatus.ACTIVE
        assert order.poster_id == a1
        assert order.node_id == _hub_id(world)
        assert order.side == BuySell.SELL
        assert order.commodity == CommodityType.IRON
        assert order.quantity == 5
        assert order.price_per_unit == 3000
        assert order.order_id in world.order_book

    def test_successful_buy_order(self, world: WorldState) -> None:
        a1, _ = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.BUY,
            commodity=CommodityType.WOOD,
            quantity=3,
            price_per_unit=4000,
        )
        assert order is not None
        assert order.status == OrderStatus.ACTIVE
        assert order.side == BuySell.BUY

    def test_order_limit_enforcement(self, world: WorldState) -> None:
        a1, _ = _agent_ids(world)
        # Post max_open_orders (5) orders
        for i in range(5):
            order = post_order(
                world,
                a1,
                side=BuySell.SELL,
                commodity=CommodityType.IRON,
                quantity=1,
                price_per_unit=1000,
            )
            assert order is not None

        # 6th order should be rejected
        order = post_order(
            world,
            a1,
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=1,
            price_per_unit=1000,
        )
        assert order is None

    def test_deterministic_order_id(self, world: WorldState) -> None:
        a1, _ = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=1,
            price_per_unit=1000,
        )
        assert order is not None
        assert order.order_id.startswith(f"order_{world.tick}_")


# ---------------------------------------------------------------------------
# 6.2 Test accept_order
# ---------------------------------------------------------------------------


class TestAcceptOrder:
    def test_successful_sell_fill(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=5,
            price_per_unit=3000,
        )
        assert order is not None

        a1_iron_before = world.agents[a1].inventory[CommodityType.IRON]
        a2_iron_before = world.agents[a2].inventory[CommodityType.IRON]
        a1_credits_before = world.agents[a1].credits
        a2_credits_before = world.agents[a2].credits

        result = accept_order(world, a2, order.order_id)

        assert result.success is True
        assert result.trade_type == "order"
        assert result.seller_id == a1
        assert result.buyer_id == a2
        assert result.credits_transferred == 15000
        assert result.items_transferred[CommodityType.IRON] == 5

        # Verify transfers
        assert world.agents[a1].inventory[CommodityType.IRON] == a1_iron_before - 5
        assert world.agents[a2].inventory[CommodityType.IRON] == a2_iron_before + 5
        assert world.agents[a1].credits == a1_credits_before + 15000
        assert world.agents[a2].credits == a2_credits_before - 15000

        # Order should be filled
        assert order.status == OrderStatus.FILLED
        world.verify_invariant()

    def test_successful_buy_fill(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.BUY,
            commodity=CommodityType.WOOD,
            quantity=3,
            price_per_unit=4000,
        )
        assert order is not None

        result = accept_order(world, a2, order.order_id)
        assert result.success is True
        assert result.buyer_id == a1  # poster is buyer
        assert result.seller_id == a2  # acceptor is seller
        assert result.credits_transferred == 12000
        world.verify_invariant()

    def test_poster_cant_cover_sell(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=5,
            price_per_unit=3000,
        )
        assert order is not None

        # Remove poster's inventory
        world.agents[a1].inventory[CommodityType.IRON] = 2

        result = accept_order(world, a2, order.order_id)
        assert result.success is False
        assert result.failure_reason == "poster cannot cover"
        assert order.status == OrderStatus.CANCELLED

    def test_acceptor_cant_cover_sell(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=5,
            price_per_unit=3000,
        )
        assert order is not None

        # Remove acceptor's credits
        world.agents[a2].credits = 5000

        result = accept_order(world, a2, order.order_id)
        assert result.success is False
        assert result.failure_reason == "acceptor cannot cover"
        # Order stays active (only poster failure cancels)
        assert order.status == OrderStatus.ACTIVE

    def test_wrong_node(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=1,
            price_per_unit=1000,
        )
        assert order is not None

        # Move acceptor to a different node
        other_node = next(
            nid for nid in world.nodes if nid != _hub_id(world)
        )
        world.agents[a2].location = other_node

        result = accept_order(world, a2, order.order_id)
        assert result.success is False
        assert result.failure_reason == "acceptor not at order node"

    def test_suspended_order_rejection(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=1,
            price_per_unit=1000,
        )
        assert order is not None

        # Suspend the order
        suspend_orders_for_agent(world, a1, _hub_id(world))
        assert order.status == OrderStatus.SUSPENDED

        result = accept_order(world, a2, order.order_id)
        assert result.success is False
        assert "SUSPENDED" in result.failure_reason


# ---------------------------------------------------------------------------
# 6.3 Test cancel_order
# ---------------------------------------------------------------------------


class TestCancelOrder:
    def test_poster_cancels(self, world: WorldState) -> None:
        a1, _ = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=1,
            price_per_unit=1000,
        )
        assert order is not None
        assert cancel_order(world, a1, order.order_id) is True
        assert order.status == OrderStatus.CANCELLED

    def test_non_poster_rejected(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        order = post_order(
            world,
            a1,
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=1,
            price_per_unit=1000,
        )
        assert order is not None
        assert cancel_order(world, a2, order.order_id) is False
        assert order.status == OrderStatus.ACTIVE


# ---------------------------------------------------------------------------
# 6.4 Test suspend/reactivate
# ---------------------------------------------------------------------------


class TestSuspendReactivate:
    def test_orders_suspend_on_departure(self, world: WorldState) -> None:
        a1, _ = _agent_ids(world)
        hub = _hub_id(world)
        o1 = post_order(world, a1, side=BuySell.SELL, commodity=CommodityType.IRON, quantity=1, price_per_unit=1000)
        o2 = post_order(world, a1, side=BuySell.BUY, commodity=CommodityType.WOOD, quantity=1, price_per_unit=1000)
        assert o1 is not None and o2 is not None

        suspend_orders_for_agent(world, a1, hub)
        assert o1.status == OrderStatus.SUSPENDED
        assert o2.status == OrderStatus.SUSPENDED

    def test_orders_reactivate_on_arrival(self, world: WorldState) -> None:
        a1, _ = _agent_ids(world)
        hub = _hub_id(world)
        o1 = post_order(world, a1, side=BuySell.SELL, commodity=CommodityType.IRON, quantity=1, price_per_unit=1000)
        assert o1 is not None

        suspend_orders_for_agent(world, a1, hub)
        assert o1.status == OrderStatus.SUSPENDED

        reactivate_orders_for_agent(world, a1, hub)
        assert o1.status == OrderStatus.ACTIVE


# ---------------------------------------------------------------------------
# 6.5 Test propose_trade
# ---------------------------------------------------------------------------


class TestProposeTrade:
    def test_successful_proposal(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 3},
            request_commodities={CommodityType.WOOD: 2},
            request_credits=1000,
        )
        assert proposal is not None
        assert proposal.status == TradeStatus.PENDING
        assert proposal.proposer_id == a1
        assert proposal.target_id == a2
        assert proposal.trade_id in world.trade_proposals

    def test_not_colocated(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        other_node = next(nid for nid in world.nodes if nid != _hub_id(world))
        world.agents[a2].location = other_node

        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 1},
        )
        assert proposal is None

    def test_insufficient_items(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 100},  # only has 10
        )
        assert proposal is None

    def test_pending_limit(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        # max_pending_trades = 3
        for _ in range(3):
            p = propose_trade(
                world,
                a1,
                a2,
                offer_commodities={CommodityType.IRON: 1},
            )
            assert p is not None

        # 4th should be rejected
        p = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 1},
        )
        assert p is None


# ---------------------------------------------------------------------------
# 6.6 Test accept_trade
# ---------------------------------------------------------------------------


class TestAcceptTrade:
    def test_successful_acceptance(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 3},
            request_commodities={CommodityType.WOOD: 2},
        )
        assert proposal is not None

        a1_iron = world.agents[a1].inventory[CommodityType.IRON]
        a2_iron = world.agents[a2].inventory[CommodityType.IRON]
        a1_wood = world.agents[a1].inventory[CommodityType.WOOD]
        a2_wood = world.agents[a2].inventory[CommodityType.WOOD]

        result = accept_trade(world, a2, proposal.trade_id)
        assert result.success is True
        assert result.trade_type == "p2p"
        assert proposal.status == TradeStatus.ACCEPTED

        # Proposer gave IRON, got WOOD
        assert world.agents[a1].inventory[CommodityType.IRON] == a1_iron - 3
        assert world.agents[a1].inventory[CommodityType.WOOD] == a1_wood + 2
        # Target got IRON, gave WOOD
        assert world.agents[a2].inventory[CommodityType.IRON] == a2_iron + 3
        assert world.agents[a2].inventory[CommodityType.WOOD] == a2_wood - 2
        world.verify_invariant()

    def test_not_colocated_anymore(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 1},
        )
        assert proposal is not None

        # Move proposer away
        other_node = next(nid for nid in world.nodes if nid != _hub_id(world))
        world.agents[a1].location = other_node

        result = accept_trade(world, a2, proposal.trade_id)
        assert result.success is False
        assert proposal.status == TradeStatus.INVALID

    def test_proposer_lacks_items(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 5},
        )
        assert proposal is not None

        # Remove proposer's inventory
        world.agents[a1].inventory[CommodityType.IRON] = 0

        result = accept_trade(world, a2, proposal.trade_id)
        assert result.success is False
        assert proposal.status == TradeStatus.INVALID

    def test_target_rejects(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 1},
        )
        assert proposal is not None

        assert reject_trade(world, a2, proposal.trade_id) is True
        assert proposal.status == TradeStatus.REJECTED

    def test_non_target_cannot_accept(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 1},
        )
        assert proposal is not None

        result = accept_trade(world, a1, proposal.trade_id)  # proposer trying to accept own
        assert result.success is False
        assert result.failure_reason == "agent is not the target"


# ---------------------------------------------------------------------------
# 6.7 Test expire_pending_trades
# ---------------------------------------------------------------------------


class TestExpireTrades:
    def test_correct_expiration(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        world.tick = 10
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 1},
        )
        assert proposal is not None

        # Not yet expired at tick 14 with max_age=5
        world.tick = 14
        expired = expire_pending_trades(world, max_age=5)
        assert len(expired) == 0
        assert proposal.status == TradeStatus.PENDING

        # Expired at tick 15
        world.tick = 15
        expired = expire_pending_trades(world, max_age=5)
        assert proposal.trade_id in expired
        assert proposal.status == TradeStatus.EXPIRED

    def test_accepted_before_expiry(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        world.tick = 10
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 1},
        )
        assert proposal is not None

        # Accept at tick 13
        world.tick = 13
        result = accept_trade(world, a2, proposal.trade_id)
        assert result.success is True

        # Expire check at tick 15 should not affect already-accepted trade
        world.tick = 15
        expired = expire_pending_trades(world, max_age=5)
        assert len(expired) == 0
        assert proposal.status == TradeStatus.ACCEPTED


# ---------------------------------------------------------------------------
# 6.8 Test P2P multi-item swaps
# ---------------------------------------------------------------------------


class TestMultiItemSwaps:
    def test_pure_commodity_swap(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 5},
            request_commodities={CommodityType.WOOD: 3},
        )
        assert proposal is not None
        result = accept_trade(world, a2, proposal.trade_id)
        assert result.success is True
        assert result.credits_transferred == 0
        world.verify_invariant()

    def test_commodity_for_credits(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 5},
            request_credits=10000,
        )
        assert proposal is not None
        result = accept_trade(world, a2, proposal.trade_id)
        assert result.success is True
        world.verify_invariant()

    def test_mixed_swap(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={CommodityType.IRON: 3},
            offer_credits=2000,
            request_commodities={CommodityType.WOOD: 5},
        )
        assert proposal is not None
        result = accept_trade(world, a2, proposal.trade_id)
        assert result.success is True
        world.verify_invariant()

    def test_empty_proposal_rejected(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        proposal = propose_trade(
            world,
            a1,
            a2,
            offer_commodities={},
            offer_credits=0,
            request_commodities={},
            request_credits=0,
        )
        assert proposal is None


# ---------------------------------------------------------------------------
# 6.9 Test settle_trade (credits and commodities transfer correctly)
# ---------------------------------------------------------------------------


class TestSettlement:
    def test_order_settlement_transfers(self, world: WorldState) -> None:
        """Verify credits and commodities move correctly in order settlement."""
        a1, a2 = _agent_ids(world)
        a1_credits = world.agents[a1].credits
        a2_credits = world.agents[a2].credits
        a1_iron = world.agents[a1].inventory[CommodityType.IRON]
        a2_iron = world.agents[a2].inventory[CommodityType.IRON]

        order = post_order(
            world, a1, side=BuySell.SELL, commodity=CommodityType.IRON,
            quantity=3, price_per_unit=5000,
        )
        assert order is not None
        result = accept_order(world, a2, order.order_id)
        assert result.success is True

        assert world.agents[a1].credits == a1_credits + 15000
        assert world.agents[a2].credits == a2_credits - 15000
        assert world.agents[a1].inventory[CommodityType.IRON] == a1_iron - 3
        assert world.agents[a2].inventory[CommodityType.IRON] == a2_iron + 3
        world.verify_invariant()

    def test_p2p_settlement_with_credits(self, world: WorldState) -> None:
        """Verify P2P trades with credits transfer correctly."""
        a1, a2 = _agent_ids(world)
        a1_credits = world.agents[a1].credits
        a2_credits = world.agents[a2].credits

        proposal = propose_trade(
            world, a1, a2,
            offer_commodities={CommodityType.IRON: 2},
            offer_credits=3000,
            request_commodities={CommodityType.WOOD: 4},
        )
        assert proposal is not None
        result = accept_trade(world, a2, proposal.trade_id)
        assert result.success is True

        # Proposer sent 3000 credits
        assert world.agents[a1].credits == a1_credits - 3000
        assert world.agents[a2].credits == a2_credits + 3000
        world.verify_invariant()


# ---------------------------------------------------------------------------
# 6.10 Test trade_history
# ---------------------------------------------------------------------------


class TestTradeHistory:
    def test_queryable_by_node(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        hub = _hub_id(world)

        # Execute 3 trades
        for _ in range(3):
            order = post_order(
                world, a1, side=BuySell.SELL, commodity=CommodityType.IRON,
                quantity=1, price_per_unit=1000,
            )
            assert order is not None
            result = accept_order(world, a2, order.order_id)
            assert result.success is True

        history = get_trade_history(world, hub)
        assert len(history) == 3

    def test_limit_respected(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        hub = _hub_id(world)

        for _ in range(10):
            order = post_order(
                world, a1, side=BuySell.SELL, commodity=CommodityType.IRON,
                quantity=1, price_per_unit=1000,
            )
            assert order is not None
            accept_order(world, a2, order.order_id)

        history = get_trade_history(world, hub, limit=5)
        assert len(history) == 5

    def test_most_recent_first(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)
        hub = _hub_id(world)

        for i in range(3):
            world.tick = i * 10
            order = post_order(
                world, a1, side=BuySell.SELL, commodity=CommodityType.IRON,
                quantity=1, price_per_unit=1000,
            )
            assert order is not None
            accept_order(world, a2, order.order_id)

        history = get_trade_history(world, hub)
        assert history[0].tick == 20  # most recent
        assert history[2].tick == 0   # oldest


# ---------------------------------------------------------------------------
# 6.11 Test cancel_all_orders_for_agent
# ---------------------------------------------------------------------------


class TestDeathCleanup:
    def test_dead_agent_orders_cancelled(self, world: WorldState) -> None:
        a1, _ = _agent_ids(world)
        hub = _hub_id(world)

        # Post 3 active orders + suspend 1
        orders = []
        for _ in range(4):
            o = post_order(
                world, a1, side=BuySell.SELL, commodity=CommodityType.IRON,
                quantity=1, price_per_unit=1000,
            )
            assert o is not None
            orders.append(o)

        # Suspend one
        orders[3].status = OrderStatus.SUSPENDED

        cancel_all_orders_for_agent(world, a1)

        for o in orders:
            assert o.status == OrderStatus.CANCELLED

    def test_dead_agent_proposals_invalidated(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)

        # Proposals where dead agent is proposer and target
        p1 = propose_trade(world, a1, a2, offer_commodities={CommodityType.IRON: 1})
        p2 = propose_trade(world, a2, a1, offer_commodities={CommodityType.WOOD: 1})
        assert p1 is not None and p2 is not None

        cancel_all_orders_for_agent(world, a1)

        assert p1.status == TradeStatus.INVALID  # a1 is proposer
        assert p2.status == TradeStatus.INVALID  # a1 is target


# ---------------------------------------------------------------------------
# 6.12 Property-based test: random operations preserve invariant
# ---------------------------------------------------------------------------


# Strategies for hypothesis
commodity_st = st.sampled_from([CommodityType.IRON, CommodityType.WOOD])
side_st = st.sampled_from([BuySell.BUY, BuySell.SELL])


@st.composite
def trade_action(draw: st.DrawFn) -> tuple[str, dict]:
    """Generate a random trading action."""
    action = draw(st.sampled_from(["post", "accept", "cancel", "propose", "accept_p2p"]))
    commodity = draw(commodity_st)
    quantity = draw(st.integers(min_value=1, max_value=5))
    price = draw(st.integers(min_value=100, max_value=10000))
    return action, {"commodity": commodity, "quantity": quantity, "price": price}


@settings(max_examples=50, deadline=None)
@given(actions=st.lists(trade_action(), min_size=1, max_size=20))
def test_random_operations_preserve_invariant(
    actions: list[tuple[str, dict]],
) -> None:
    """Random sequences of trading operations never violate the fixed-supply invariant."""
    config = WorldConfig(
        num_nodes=5,
        num_commodity_types=2,
        population_size=2,
        total_credit_supply=10_000_000,
        starting_credits=100_000,
        max_open_orders=10,
        max_pending_trades=10,
    )
    world = generate_world(config, seed=42)

    ids = sorted(world.agents.keys())
    a1, a2 = ids[0], ids[1]

    # Put agents together at a hub with inventory
    hub = next(nid for nid, n in world.nodes.items() if n.node_type.value == "TRADE_HUB")
    for agent in world.agents.values():
        agent.location = hub
        agent.inventory[CommodityType.IRON] = 50
        agent.inventory[CommodityType.WOOD] = 50

    for action_type, params in actions:
        if action_type == "post":
            post_order(
                world, a1,
                side=BuySell.SELL,
                commodity=params["commodity"],
                quantity=params["quantity"],
                price_per_unit=params["price"],
            )
        elif action_type == "accept":
            # Try to accept first active order
            active = [
                o for o in world.order_book.values()
                if getattr(o, "status", None) == OrderStatus.ACTIVE
            ]
            if active:
                accept_order(world, a2, active[0].order_id)
        elif action_type == "cancel":
            agent_orders = [
                o for o in world.order_book.values()
                if getattr(o, "poster_id", None) == a1
                and getattr(o, "status", None) == OrderStatus.ACTIVE
            ]
            if agent_orders:
                cancel_order(world, a1, agent_orders[0].order_id)
        elif action_type == "propose":
            propose_trade(
                world, a1, a2,
                offer_commodities={params["commodity"]: params["quantity"]},
                request_credits=params["price"],
            )
        elif action_type == "accept_p2p":
            pending = [
                p for p in world.trade_proposals.values()
                if getattr(p, "status", None) == TradeStatus.PENDING
                and getattr(p, "target_id", None) == a2
            ]
            if pending:
                accept_trade(world, a2, pending[0].trade_id)

        # Invariant must hold after every operation
        world.verify_invariant()


# ---------------------------------------------------------------------------
# 6.13 Test WorldState serialization round-trip with trading state
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_round_trip_with_orders(self, world: WorldState) -> None:
        a1, a2 = _agent_ids(world)

        # Create some orders
        post_order(
            world, a1, side=BuySell.SELL, commodity=CommodityType.IRON,
            quantity=3, price_per_unit=5000,
        )
        propose_trade(
            world, a1, a2,
            offer_commodities={CommodityType.IRON: 1},
            request_credits=2000,
        )

        # Execute a trade for history
        order = post_order(
            world, a1, side=BuySell.SELL, commodity=CommodityType.IRON,
            quantity=1, price_per_unit=1000,
        )
        assert order is not None
        accept_order(world, a2, order.order_id)

        # Serialize and deserialize
        data = world.to_json()
        restored = WorldState.from_json(data)

        # Verify trading state survived
        assert len(restored.order_book) == len(world.order_book)
        assert len(restored.trade_proposals) == len(world.trade_proposals)
        assert len(restored.trade_history) == len(world.trade_history)
        assert restored.next_order_seq == world.next_order_seq

        # Verify order data
        for oid, orig in world.order_book.items():
            rest = restored.order_book[oid]
            assert getattr(rest, "order_id", None) == getattr(orig, "order_id", None)
            assert getattr(rest, "status", None) == getattr(orig, "status", None)

        # Verify trade history data
        hub = _hub_id(world)
        if hub in world.trade_history:
            orig_hist = world.trade_history[hub]
            rest_hist = restored.trade_history[hub]
            assert len(rest_hist) == len(orig_hist)
            for oh, rh in zip(orig_hist, rest_hist):
                assert oh.success == rh.success
                assert oh.tick == rh.tick

        restored.verify_invariant()
