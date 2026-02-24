"""Tests for the action system: types, validation, and resolution."""

from __future__ import annotations

import random

import pytest
from pydantic import TypeAdapter, ValidationError

from evomarket.core.agent import Agent
from evomarket.core.types import CommodityType, NodeType
from evomarket.core.world import Node, WorldConfig, WorldState
from evomarket.engine.actions import (
    AcceptOrderAction,
    AcceptTradeAction,
    Action,
    ActionResult,
    AgentTurnResult,
    HarvestAction,
    IdleAction,
    InspectAction,
    MoveAction,
    PostOrderAction,
    ProposeTradeAction,
    SendMessageAction,
    UpdateWillAction,
    resolve_actions,
    validate_action,
)
from evomarket.engine.trading import (
    BuySell,
    OrderStatus,
    TradeStatus,
    post_order,
    propose_trade,
)


# ============================================================================
# Test World Fixture
# ============================================================================


def _make_test_world(seed: int = 42) -> WorldState:
    """Create a minimal test world with known topology.

    Topology:
        node_spawn <-> node_iron <-> node_wood
            ^                            ^
            |____________________________|

    Agents:
        agent_000: at node_spawn, 30000 credits, empty inventory
        agent_001: at node_iron,  30000 credits, 5 IRON + 2 WOOD
        agent_002: at node_iron,  30000 credits, 3 IRON
    """
    nodes = {
        "node_spawn": Node(
            node_id="node_spawn",
            name="Spawn",
            node_type=NodeType.SPAWN,
            resource_distribution={},
            resource_spawn_rate=0.0,
            resource_stockpile={},
            resource_cap=0,
            npc_buys=[],
            npc_base_prices={},
            npc_stockpile={},
            npc_stockpile_capacity=0,
            npc_budget=0,
            adjacent_nodes=["node_iron", "node_wood"],
        ),
        "node_iron": Node(
            node_id="node_iron",
            name="Iron Mine",
            node_type=NodeType.RESOURCE,
            resource_distribution={CommodityType.IRON: 0.8, CommodityType.WOOD: 0.2},
            resource_spawn_rate=0.5,
            resource_stockpile={CommodityType.IRON: 5.5, CommodityType.WOOD: 1.2},
            resource_cap=20,
            npc_buys=[CommodityType.IRON],
            npc_base_prices={CommodityType.IRON: 5000},
            npc_stockpile={CommodityType.IRON: 0},
            npc_stockpile_capacity=50,
            npc_budget=100_000,
            adjacent_nodes=["node_spawn", "node_wood"],
        ),
        "node_wood": Node(
            node_id="node_wood",
            name="Wood Forest",
            node_type=NodeType.RESOURCE,
            resource_distribution={CommodityType.IRON: 0.1, CommodityType.WOOD: 0.7},
            resource_spawn_rate=0.5,
            resource_stockpile={CommodityType.IRON: 0.3, CommodityType.WOOD: 3.8},
            resource_cap=20,
            npc_buys=[CommodityType.WOOD],
            npc_base_prices={CommodityType.WOOD: 5000},
            npc_stockpile={CommodityType.WOOD: 0},
            npc_stockpile_capacity=50,
            npc_budget=100_000,
            adjacent_nodes=["node_spawn", "node_iron"],
        ),
    }

    agents = {
        "agent_000": Agent(
            agent_id="agent_000",
            display_name="Agent 0",
            location="node_spawn",
            credits=30_000,
            inventory={CommodityType.IRON: 0, CommodityType.WOOD: 0},
            age=0,
            alive=True,
            will={},
        ),
        "agent_001": Agent(
            agent_id="agent_001",
            display_name="Agent 1",
            location="node_iron",
            credits=30_000,
            inventory={CommodityType.IRON: 5, CommodityType.WOOD: 2},
            age=10,
            alive=True,
            will={},
        ),
        "agent_002": Agent(
            agent_id="agent_002",
            display_name="Agent 2",
            location="node_iron",
            credits=30_000,
            inventory={CommodityType.IRON: 3, CommodityType.WOOD: 0},
            age=5,
            alive=True,
            will={},
        ),
    }

    config = WorldConfig(
        num_nodes=3,
        num_commodity_types=2,
        population_size=3,
        total_credit_supply=1_000_000,
        starting_credits=30_000,
    )

    total_agent_credits = sum(a.credits for a in agents.values())
    total_npc_budgets = sum(n.npc_budget for n in nodes.values())
    treasury = config.total_credit_supply - total_agent_credits - total_npc_budgets

    return WorldState(
        nodes=nodes,
        agents=agents,
        treasury=treasury,
        total_supply=config.total_credit_supply,
        tick=0,
        next_agent_id=3,
        config=config,
        rng=random.Random(seed),
    )


@pytest.fixture
def world() -> WorldState:
    """Fresh test world for each test."""
    w = _make_test_world()
    w.verify_invariant()
    return w


# ============================================================================
# Action Model Construction and Serialization
# ============================================================================


class TestActionModels:
    """Test all action model construction and discriminated union round-trip."""

    def test_move_action(self) -> None:
        a = MoveAction(target_node="node_iron")
        assert a.action_type == "move"
        assert a.target_node == "node_iron"

    def test_harvest_action(self) -> None:
        a = HarvestAction()
        assert a.action_type == "harvest"

    def test_post_order_action(self) -> None:
        a = PostOrderAction(
            side="sell", commodity=CommodityType.IRON, quantity=3, price=5000
        )
        assert a.action_type == "post_order"
        assert a.side == "sell"
        assert a.commodity == CommodityType.IRON
        assert a.quantity == 3
        assert a.price == 5000

    def test_accept_order_action(self) -> None:
        a = AcceptOrderAction(order_id="order_001")
        assert a.action_type == "accept_order"
        assert a.order_id == "order_001"

    def test_propose_trade_action(self) -> None:
        a = ProposeTradeAction(
            target_agent="agent_002",
            offer={CommodityType.IRON.value: 5},
            request={"credits": 3000},
        )
        assert a.action_type == "propose_trade"
        assert a.offer == {"IRON": 5}
        assert a.request == {"credits": 3000}

    def test_accept_trade_action(self) -> None:
        a = AcceptTradeAction(trade_id="trade_042")
        assert a.action_type == "accept_trade"
        assert a.trade_id == "trade_042"

    def test_send_message_action_broadcast(self) -> None:
        a = SendMessageAction(target="all", text="hello")
        assert a.action_type == "send_message"
        assert a.target == "all"
        assert a.text == "hello"

    def test_update_will_action(self) -> None:
        a = UpdateWillAction(distribution={"agent_001": 0.5, "agent_002": 0.5})
        assert a.action_type == "update_will"
        assert a.distribution == {"agent_001": 0.5, "agent_002": 0.5}

    def test_inspect_action(self) -> None:
        a = InspectAction(target_agent="agent_005")
        assert a.action_type == "inspect"
        assert a.target_agent == "agent_005"

    def test_idle_action(self) -> None:
        a = IdleAction()
        assert a.action_type == "idle"

    def test_discriminated_union_deserialization(self) -> None:
        adapter = TypeAdapter(Action)
        data = {"action_type": "move", "target_node": "node_iron_peak"}
        result = adapter.validate_python(data)
        assert isinstance(result, MoveAction)
        assert result.target_node == "node_iron_peak"

    def test_discriminated_union_round_trip(self) -> None:
        adapter = TypeAdapter(Action)
        actions = [
            MoveAction(target_node="node_a"),
            HarvestAction(),
            PostOrderAction(
                side="buy", commodity=CommodityType.WOOD, quantity=2, price=3000
            ),
            IdleAction(),
        ]
        for original in actions:
            serialized = original.model_dump(mode="json")
            restored = adapter.validate_python(serialized)
            assert type(restored) is type(original)
            assert restored == original

    def test_agent_turn_result_with_scratchpad(self) -> None:
        result = AgentTurnResult(action=IdleAction(), scratchpad_update="notes")
        assert result.scratchpad_update == "notes"
        assert isinstance(result.action, IdleAction)

    def test_agent_turn_result_without_scratchpad(self) -> None:
        result = AgentTurnResult(action=MoveAction(target_node="n"))
        assert result.scratchpad_update is None

    def test_action_result_success(self) -> None:
        r = ActionResult(
            agent_id="agent_001",
            action=HarvestAction(),
            success=True,
            detail="Harvested 1 IRON",
        )
        assert r.success is True

    def test_action_result_failure(self) -> None:
        r = ActionResult(
            agent_id="agent_001",
            action=HarvestAction(),
            success=False,
            detail="No stock",
        )
        assert r.success is False


# ============================================================================
# Pydantic Validators
# ============================================================================


class TestPydanticValidators:
    """Test Pydantic validators on action models."""

    def test_update_will_negative_percentage(self) -> None:
        with pytest.raises(ValidationError):
            UpdateWillAction(distribution={"agent_001": -0.1})

    def test_update_will_sum_over_one(self) -> None:
        with pytest.raises(ValidationError):
            UpdateWillAction(distribution={"agent_001": 0.6, "agent_002": 0.6})

    def test_update_will_valid(self) -> None:
        a = UpdateWillAction(distribution={"agent_001": 0.5, "agent_002": 0.5})
        assert sum(a.distribution.values()) == 1.0

    def test_post_order_zero_quantity(self) -> None:
        with pytest.raises(ValidationError):
            PostOrderAction(
                side="buy", commodity=CommodityType.IRON, quantity=0, price=5000
            )

    def test_post_order_negative_price(self) -> None:
        with pytest.raises(ValidationError):
            PostOrderAction(
                side="sell", commodity=CommodityType.IRON, quantity=1, price=-100
            )

    def test_propose_trade_invalid_key(self) -> None:
        with pytest.raises(ValidationError):
            ProposeTradeAction(
                target_agent="agent_002",
                offer={"GOLD": 5},
                request={"credits": 1000},
            )

    def test_propose_trade_zero_quantity(self) -> None:
        with pytest.raises(ValidationError):
            ProposeTradeAction(
                target_agent="agent_002",
                offer={"IRON": 0},
                request={"credits": 1000},
            )


# ============================================================================
# Validation Tests
# ============================================================================


class TestValidation:
    """Test validate_action for each action type."""

    # --- Move ---

    def test_move_valid(self, world: WorldState) -> None:
        action = MoveAction(target_node="node_iron")
        result = validate_action("agent_000", action, world)
        assert isinstance(result, MoveAction)

    def test_move_non_adjacent(self, world: WorldState) -> None:
        action = MoveAction(target_node="node_nonexistent")
        result = validate_action("agent_000", action, world)
        assert isinstance(result, IdleAction)

    def test_move_nonexistent_node(self, world: WorldState) -> None:
        action = MoveAction(target_node="node_doesnt_exist")
        result = validate_action("agent_000", action, world)
        assert isinstance(result, IdleAction)

    # --- Harvest ---

    def test_harvest_valid(self, world: WorldState) -> None:
        action = HarvestAction()
        result = validate_action("agent_001", action, world)
        assert isinstance(result, HarvestAction)

    def test_harvest_at_non_resource(self, world: WorldState) -> None:
        action = HarvestAction()
        result = validate_action("agent_000", action, world)
        assert isinstance(result, IdleAction)

    def test_harvest_no_stock(self, world: WorldState) -> None:
        node = world.nodes["node_iron"]
        for c in node.resource_stockpile:
            node.resource_stockpile[c] = 0.3
        action = HarvestAction()
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    # --- PostOrder ---

    def test_post_sell_order_valid(self, world: WorldState) -> None:
        action = PostOrderAction(
            side="sell", commodity=CommodityType.IRON, quantity=3, price=5000
        )
        result = validate_action("agent_001", action, world)
        assert isinstance(result, PostOrderAction)

    def test_post_sell_order_insufficient(self, world: WorldState) -> None:
        action = PostOrderAction(
            side="sell", commodity=CommodityType.IRON, quantity=10, price=5000
        )
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    def test_post_buy_order_valid(self, world: WorldState) -> None:
        action = PostOrderAction(
            side="buy", commodity=CommodityType.IRON, quantity=3, price=5000
        )
        result = validate_action("agent_001", action, world)
        assert isinstance(result, PostOrderAction)

    def test_post_buy_order_insufficient_credits(self, world: WorldState) -> None:
        action = PostOrderAction(
            side="buy", commodity=CommodityType.IRON, quantity=10, price=5000
        )
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    def test_post_order_max_limit(self, world: WorldState) -> None:
        # Fill up max open orders using trading module
        for i in range(world.config.max_open_orders):
            post_order(
                world,
                "agent_001",
                side=BuySell.SELL,
                commodity=CommodityType.IRON,
                quantity=1,
                price_per_unit=1000,
            )
        action = PostOrderAction(
            side="sell", commodity=CommodityType.IRON, quantity=1, price=1000
        )
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    # --- AcceptOrder ---

    def test_accept_order_valid(self, world: WorldState) -> None:
        # Create a sell order at node_iron using trading module
        order = post_order(
            world,
            "agent_001",
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=2,
            price_per_unit=5000,
        )
        assert order is not None
        action = AcceptOrderAction(order_id=order.order_id)
        result = validate_action("agent_002", action, world)
        assert isinstance(result, AcceptOrderAction)

    def test_accept_order_nonexistent(self, world: WorldState) -> None:
        action = AcceptOrderAction(order_id="order_999")
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    def test_accept_order_wrong_node(self, world: WorldState) -> None:
        # Move agent_000 to node_wood and post order there
        world.agents["agent_000"].location = "node_wood"
        world.agents["agent_000"].inventory[CommodityType.WOOD] = 5
        order = post_order(
            world,
            "agent_000",
            side=BuySell.SELL,
            commodity=CommodityType.WOOD,
            quantity=1,
            price_per_unit=1000,
        )
        assert order is not None
        # agent_001 at node_iron tries to accept order at node_wood
        action = AcceptOrderAction(order_id=order.order_id)
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    # --- ProposeTrade ---

    def test_propose_trade_valid(self, world: WorldState) -> None:
        action = ProposeTradeAction(
            target_agent="agent_002",
            offer={"IRON": 2},
            request={"credits": 5000},
        )
        result = validate_action("agent_001", action, world)
        assert isinstance(result, ProposeTradeAction)

    def test_propose_trade_different_node(self, world: WorldState) -> None:
        action = ProposeTradeAction(
            target_agent="agent_001",
            offer={"credits": 5000},
            request={"IRON": 1},
        )
        result = validate_action("agent_000", action, world)
        assert isinstance(result, IdleAction)

    def test_propose_trade_self(self, world: WorldState) -> None:
        action = ProposeTradeAction(
            target_agent="agent_001",
            offer={"IRON": 1},
            request={"credits": 1000},
        )
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    def test_propose_trade_insufficient_offer(self, world: WorldState) -> None:
        action = ProposeTradeAction(
            target_agent="agent_001",
            offer={"IRON": 10},
            request={"credits": 1000},
        )
        result = validate_action("agent_002", action, world)
        assert isinstance(result, IdleAction)

    def test_propose_trade_dead_target(self, world: WorldState) -> None:
        world.agents["agent_002"].alive = False
        action = ProposeTradeAction(
            target_agent="agent_002",
            offer={"IRON": 1},
            request={"credits": 1000},
        )
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    # --- AcceptTrade ---

    def test_accept_trade_valid(self, world: WorldState) -> None:
        # Create a trade proposal using trading module
        proposal = propose_trade(
            world,
            "agent_001",
            "agent_002",
            offer_commodities={CommodityType.IRON: 2},
            request_credits=5000,
        )
        assert proposal is not None
        action = AcceptTradeAction(trade_id=proposal.trade_id)
        result = validate_action("agent_002", action, world)
        assert isinstance(result, AcceptTradeAction)

    def test_accept_trade_not_for_agent(self, world: WorldState) -> None:
        proposal = propose_trade(
            world,
            "agent_001",
            "agent_002",
            offer_commodities={CommodityType.IRON: 2},
            request_credits=5000,
        )
        assert proposal is not None
        # agent_001 tries to accept a trade targeted at agent_002
        action = AcceptTradeAction(trade_id=proposal.trade_id)
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    def test_accept_trade_nonexistent(self, world: WorldState) -> None:
        action = AcceptTradeAction(trade_id="trade_999")
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    # --- SendMessage ---

    def test_send_message_broadcast(self, world: WorldState) -> None:
        action = SendMessageAction(target="all", text="hi")
        result = validate_action("agent_001", action, world)
        assert isinstance(result, SendMessageAction)

    def test_send_message_direct_same_node(self, world: WorldState) -> None:
        action = SendMessageAction(target="agent_002", text="hi")
        result = validate_action("agent_001", action, world)
        assert isinstance(result, SendMessageAction)

    def test_send_message_direct_different_node(self, world: WorldState) -> None:
        action = SendMessageAction(target="agent_001", text="hi")
        result = validate_action("agent_000", action, world)
        assert isinstance(result, IdleAction)

    # --- UpdateWill ---

    def test_update_will_valid(self, world: WorldState) -> None:
        action = UpdateWillAction(distribution={"agent_001": 0.5, "agent_002": 0.5})
        result = validate_action("agent_000", action, world)
        assert isinstance(result, UpdateWillAction)

    def test_update_will_nonexistent_beneficiary(self, world: WorldState) -> None:
        action = UpdateWillAction(distribution={"agent_999": 1.0})
        result = validate_action("agent_000", action, world)
        assert isinstance(result, IdleAction)

    # --- Inspect ---

    def test_inspect_valid(self, world: WorldState) -> None:
        action = InspectAction(target_agent="agent_002")
        result = validate_action("agent_001", action, world)
        assert isinstance(result, InspectAction)

    def test_inspect_different_node(self, world: WorldState) -> None:
        action = InspectAction(target_agent="agent_000")
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    def test_inspect_dead_agent(self, world: WorldState) -> None:
        world.agents["agent_002"].alive = False
        action = InspectAction(target_agent="agent_002")
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    # --- Idle ---

    def test_idle_always_valid(self, world: WorldState) -> None:
        action = IdleAction()
        result = validate_action("agent_000", action, world)
        assert isinstance(result, IdleAction)

    # --- Dead agent ---

    def test_dead_agent_action_becomes_idle(self, world: WorldState) -> None:
        world.agents["agent_001"].alive = False
        action = HarvestAction()
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)


# ============================================================================
# Harvest Conflict Resolution
# ============================================================================


class TestHarvestResolution:
    """Test harvest action resolution including conflicts."""

    def test_single_harvest(self, world: WorldState) -> None:
        actions: dict[str, Action] = {"agent_001": HarvestAction()}
        results = resolve_actions(world, actions)
        assert len(results) == 1
        assert results[0].success is True
        assert "IRON" in results[0].detail  # IRON has highest floor(5.5) = 5

    def test_harvest_updates_state(self, world: WorldState) -> None:
        initial_iron = world.nodes["node_iron"].resource_stockpile[CommodityType.IRON]
        initial_inv = world.agents["agent_001"].inventory[CommodityType.IRON]
        actions: dict[str, Action] = {"agent_001": HarvestAction()}
        resolve_actions(world, actions)
        assert (
            world.nodes["node_iron"].resource_stockpile[CommodityType.IRON]
            == initial_iron - 1.0
        )
        assert (
            world.agents["agent_001"].inventory[CommodityType.IRON] == initial_inv + 1
        )

    def test_harvest_conflict_stock_depletion(self, world: WorldState) -> None:
        """Multiple agents harvest, only those with priority get resources."""
        node = world.nodes["node_iron"]
        node.resource_stockpile[CommodityType.IRON] = 1.5
        node.resource_stockpile[CommodityType.WOOD] = 0.3

        actions: dict[str, Action] = {
            "agent_001": HarvestAction(),
            "agent_002": HarvestAction(),
        }
        results = resolve_actions(world, actions)

        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        assert len(successes) == 1
        assert len(failures) == 1

    def test_harvest_selects_highest_stockpile(self, world: WorldState) -> None:
        """Harvest should pick the commodity with highest floor(stockpile)."""
        node = world.nodes["node_iron"]
        node.resource_stockpile[CommodityType.IRON] = 1.8
        node.resource_stockpile[CommodityType.WOOD] = 3.5

        actions: dict[str, Action] = {"agent_001": HarvestAction()}
        results = resolve_actions(world, actions)
        assert results[0].success is True
        assert "WOOD" in results[0].detail


# ============================================================================
# AcceptOrder Conflict Resolution
# ============================================================================


class TestAcceptOrderConflict:
    """Test AcceptOrder conflict when multiple agents accept the same order."""

    def test_single_accept(self, world: WorldState) -> None:
        # Create a sell order using trading module
        order = post_order(
            world,
            "agent_001",
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=2,
            price_per_unit=5000,
        )
        assert order is not None

        actions: dict[str, Action] = {
            "agent_002": AcceptOrderAction(order_id=order.order_id),
        }
        results = resolve_actions(world, actions)
        assert results[0].success is True
        # Order should be filled
        assert world.order_book[order.order_id].status == OrderStatus.FILLED

    def test_multiple_accept_conflict(self, world: WorldState) -> None:
        """Two agents accept the same order; priority wins."""
        world.agents["agent_000"].location = "node_iron"

        order = post_order(
            world,
            "agent_001",
            side=BuySell.SELL,
            commodity=CommodityType.IRON,
            quantity=1,
            price_per_unit=5000,
        )
        assert order is not None

        actions: dict[str, Action] = {
            "agent_000": AcceptOrderAction(order_id=order.order_id),
            "agent_002": AcceptOrderAction(order_id=order.order_id),
        }
        results = resolve_actions(world, actions)

        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        assert len(successes) == 1
        assert len(failures) == 1


# ============================================================================
# Trade Lifecycle
# ============================================================================


class TestTradeLifecycle:
    """Test propose → accept → items exchanged."""

    def test_full_trade_lifecycle(self, world: WorldState) -> None:
        """agent_001 proposes trade to agent_002, then agent_002 accepts."""
        initial_iron_002 = world.agents["agent_002"].inventory[CommodityType.IRON]
        initial_credits_002 = world.agents["agent_002"].credits

        # Step 1: Propose trade (agent_001 offers 2 IRON, requests 5000 credits)
        propose_actions: dict[str, Action] = {
            "agent_001": ProposeTradeAction(
                target_agent="agent_002",
                offer={"IRON": 2},
                request={"credits": 5000},
            ),
        }
        results = resolve_actions(world, propose_actions)
        assert results[0].success is True
        world.verify_invariant()

        # Find the trade proposal
        pending = [
            tid
            for tid, p in world.trade_proposals.items()
            if getattr(p, "status", None) == TradeStatus.PENDING
        ]
        assert len(pending) == 1
        trade_id = pending[0]

        # Step 2: Accept trade
        accept_actions: dict[str, Action] = {
            "agent_002": AcceptTradeAction(trade_id=trade_id),
        }
        results = resolve_actions(world, accept_actions)
        assert results[0].success is True

        # agent_002 received 2 IRON and paid 5000 credits
        assert (
            world.agents["agent_002"].inventory[CommodityType.IRON]
            == initial_iron_002 + 2
        )
        assert world.agents["agent_002"].credits == initial_credits_002 - 5000
        world.verify_invariant()

    def test_trade_with_credits_offer(self, world: WorldState) -> None:
        """Test trade where the offer includes credits."""
        propose_actions: dict[str, Action] = {
            "agent_001": ProposeTradeAction(
                target_agent="agent_002",
                offer={"credits": 10000},
                request={"IRON": 2},
            ),
        }
        results = resolve_actions(world, propose_actions)
        assert results[0].success is True
        world.verify_invariant()


# ============================================================================
# NPC Sell Resolution
# ============================================================================


class TestNpcSellResolution:
    """Test NPC auto-fill of sell orders."""

    def test_npc_fills_sell_order(self, world: WorldState) -> None:
        """Sell order at node with NPC buyer gets auto-filled."""
        initial_credits = world.agents["agent_001"].credits

        actions: dict[str, Action] = {
            "agent_001": PostOrderAction(
                side="sell", commodity=CommodityType.IRON, quantity=1, price=5000
            ),
        }
        results = resolve_actions(world, actions)
        assert results[0].success is True

        # NPC should have auto-filled via iterative pricing
        # base price * (cap - stockpile) / cap = 5000 * (50-0) / 50 = 5000
        npc_price = 5000 * (50 - 0) // 50
        assert world.agents["agent_001"].credits == initial_credits + npc_price
        assert world.nodes["node_iron"].npc_stockpile[CommodityType.IRON] == 1

    def test_npc_insufficient_budget(self, world: WorldState) -> None:
        """NPC can't fill if budget is too low."""
        world.nodes["node_iron"].npc_budget = 0
        world.treasury = (
            world.total_supply
            - sum(a.credits for a in world.agents.values())
            - sum(n.npc_budget for n in world.nodes.values())
        )

        actions: dict[str, Action] = {
            "agent_001": PostOrderAction(
                side="sell", commodity=CommodityType.IRON, quantity=1, price=5000
            ),
        }
        resolve_actions(world, actions)
        # The order was posted but NPC couldn't fill — order should still exist
        sell_orders = [
            o
            for o in world.order_book.values()
            if getattr(o, "status", None) == OrderStatus.ACTIVE
            and getattr(o, "side", None) == BuySell.SELL
        ]
        assert len(sell_orders) == 1

    def test_npc_pricing_supply_responsive(self, world: WorldState) -> None:
        """NPC price decreases as stockpile increases."""
        node = world.nodes["node_iron"]
        node.npc_stockpile[CommodityType.IRON] = 25
        expected_price = 5000 * (50 - 25) // 50

        actual_price = world.get_npc_price("node_iron", CommodityType.IRON)
        assert actual_price == expected_price


# ============================================================================
# Determinism
# ============================================================================


class TestDeterminism:
    """Test that same seed produces identical results."""

    def test_same_seed_same_results(self) -> None:
        """Two worlds with same seed and same actions produce identical results."""
        actions: dict[str, Action] = {
            "agent_001": HarvestAction(),
            "agent_002": MoveAction(target_node="node_wood"),
        }

        world1 = _make_test_world(seed=42)
        results1 = resolve_actions(world1, dict(actions))

        world2 = _make_test_world(seed=42)
        results2 = resolve_actions(world2, dict(actions))

        for r1, r2 in zip(results1, results2):
            assert r1.agent_id == r2.agent_id
            assert r1.success == r2.success
            assert r1.detail == r2.detail

    def test_different_seed_may_differ(self) -> None:
        """Different seeds can produce different priority orderings."""
        actions: dict[str, Action] = {
            "agent_001": HarvestAction(),
            "agent_002": HarvestAction(),
        }

        outcomes: set[str] = set()
        for seed in range(100):
            world = _make_test_world(seed=seed)
            world.nodes["node_iron"].resource_stockpile[CommodityType.IRON] = 1.5
            world.nodes["node_iron"].resource_stockpile[CommodityType.WOOD] = 0.3
            results = resolve_actions(world, dict(actions))
            winner = next(r.agent_id for r in results if r.success)
            outcomes.add(winner)

        assert len(outcomes) == 2


# ============================================================================
# Fixed-Supply Invariant
# ============================================================================


class TestInvariantPreservation:
    """Test that the fixed-supply invariant holds after mixed actions."""

    def test_invariant_after_moves(self, world: WorldState) -> None:
        actions: dict[str, Action] = {
            "agent_000": MoveAction(target_node="node_iron"),
            "agent_001": MoveAction(target_node="node_wood"),
            "agent_002": MoveAction(target_node="node_spawn"),
        }
        resolve_actions(world, actions)
        world.verify_invariant()

    def test_invariant_after_harvest(self, world: WorldState) -> None:
        actions: dict[str, Action] = {
            "agent_001": HarvestAction(),
            "agent_002": HarvestAction(),
        }
        resolve_actions(world, actions)
        world.verify_invariant()

    def test_invariant_after_orders(self, world: WorldState) -> None:
        actions: dict[str, Action] = {
            "agent_001": PostOrderAction(
                side="sell", commodity=CommodityType.IRON, quantity=2, price=5000
            ),
            "agent_002": PostOrderAction(
                side="buy", commodity=CommodityType.WOOD, quantity=1, price=3000
            ),
        }
        resolve_actions(world, actions)
        world.verify_invariant()

    def test_invariant_after_trade(self, world: WorldState) -> None:
        propose: dict[str, Action] = {
            "agent_001": ProposeTradeAction(
                target_agent="agent_002",
                offer={"IRON": 2},
                request={"credits": 5000},
            ),
        }
        resolve_actions(world, propose)
        world.verify_invariant()

        pending = [
            tid
            for tid, p in world.trade_proposals.items()
            if getattr(p, "status", None) == TradeStatus.PENDING
        ]
        trade_id = pending[0]

        accept: dict[str, Action] = {
            "agent_002": AcceptTradeAction(trade_id=trade_id),
        }
        resolve_actions(world, accept)
        world.verify_invariant()

    def test_invariant_after_mixed_actions(self, world: WorldState) -> None:
        actions: dict[str, Action] = {
            "agent_000": MoveAction(target_node="node_iron"),
            "agent_001": HarvestAction(),
            "agent_002": PostOrderAction(
                side="sell", commodity=CommodityType.IRON, quantity=1, price=3000
            ),
        }
        resolve_actions(world, actions)
        world.verify_invariant()

    def test_invariant_after_buy_order_escrow(self, world: WorldState) -> None:
        """Buy order escrow moves credits to treasury; invariant holds."""
        actions: dict[str, Action] = {
            "agent_001": PostOrderAction(
                side="buy", commodity=CommodityType.IRON, quantity=2, price=5000
            ),
        }
        resolve_actions(world, actions)
        world.verify_invariant()


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases: zero balance, self-trades, dead agents, etc."""

    def test_zero_balance_buy_order(self, world: WorldState) -> None:
        """Agent with zero credits can't post buy order."""
        world.agents["agent_001"].credits = 0
        world.treasury += 30_000
        action = PostOrderAction(
            side="buy", commodity=CommodityType.IRON, quantity=1, price=1000
        )
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    def test_dead_agent_action(self, world: WorldState) -> None:
        """Dead agents' actions become idle."""
        world.agents["agent_001"].alive = False
        action = HarvestAction()
        result = validate_action("agent_001", action, world)
        assert isinstance(result, IdleAction)

    def test_empty_actions(self, world: WorldState) -> None:
        """Resolving empty actions dict returns empty results."""
        results = resolve_actions(world, {})
        assert results == []

    def test_nonexistent_agent_validation(self, world: WorldState) -> None:
        """Validation for nonexistent agent returns idle."""
        action = IdleAction()
        result = validate_action("agent_999", action, world)
        assert isinstance(result, IdleAction)

    def test_accept_trade_insufficient_after_propose(self, world: WorldState) -> None:
        """Accept trade fails if acceptor no longer has required items."""
        # Create a pending trade requesting 50000 credits from agent_002
        proposal = propose_trade(
            world,
            "agent_001",
            "agent_002",
            offer_commodities={CommodityType.IRON: 1},
            request_credits=50000,
        )
        assert proposal is not None
        # agent_002 only has 30000 credits — validation should reject
        action = AcceptTradeAction(trade_id=proposal.trade_id)
        result = validate_action("agent_002", action, world)
        assert isinstance(result, IdleAction)

    def test_resolution_with_all_action_types(self, world: WorldState) -> None:
        """Resolve a mix of different action types in one tick."""
        world.agents["agent_000"].location = "node_iron"

        actions: dict[str, Action] = {
            "agent_000": SendMessageAction(target="all", text="hello"),
            "agent_001": HarvestAction(),
            "agent_002": InspectAction(target_agent="agent_001"),
        }
        results = resolve_actions(world, actions)
        assert len(results) == 3
        assert all(r.success for r in results)
        world.verify_invariant()

    def test_order_lifecycle_sell_then_accept(self, world: WorldState) -> None:
        """Full order lifecycle: post sell → accept → items transferred."""
        initial_credits_002 = world.agents["agent_002"].credits

        # Post sell order for WOOD at node_iron (NPC doesn't buy WOOD there)
        actions: dict[str, Action] = {
            "agent_001": PostOrderAction(
                side="sell", commodity=CommodityType.WOOD, quantity=2, price=4000
            ),
        }
        results = resolve_actions(world, actions)
        assert results[0].success is True

        # Find the active order
        active_orders = [
            oid
            for oid, o in world.order_book.items()
            if getattr(o, "status", None) == OrderStatus.ACTIVE
        ]
        assert len(active_orders) == 1
        order_id = active_orders[0]

        # agent_002 accepts the sell order
        actions = {
            "agent_002": AcceptOrderAction(order_id=order_id),
        }
        results = resolve_actions(world, actions)
        assert results[0].success is True
        # agent_002 paid and received WOOD
        assert world.agents["agent_002"].inventory[CommodityType.WOOD] == 2
        assert world.agents["agent_002"].credits == initial_credits_002 - 8000
        world.verify_invariant()

    def test_buy_order_lifecycle(self, world: WorldState) -> None:
        """Post buy order → accept → credits and commodity exchanged."""
        actions: dict[str, Action] = {
            "agent_001": PostOrderAction(
                side="buy", commodity=CommodityType.WOOD, quantity=1, price=5000
            ),
        }
        resolve_actions(world, actions)
        world.verify_invariant()

        active_orders = [
            oid
            for oid, o in world.order_book.items()
            if getattr(o, "status", None) == OrderStatus.ACTIVE
        ]
        assert len(active_orders) == 1
        order_id = active_orders[0]

        # Give agent_002 some WOOD
        world.agents["agent_002"].inventory[CommodityType.WOOD] = 5

        # agent_002 accepts (sells their WOOD to fill the buy order)
        actions = {
            "agent_002": AcceptOrderAction(order_id=order_id),
        }
        resolve_actions(world, actions)
        assert world.agents["agent_002"].inventory[CommodityType.WOOD] == 4
        assert world.agents["agent_002"].credits == 30_000 + 5000
        assert world.agents["agent_001"].inventory[CommodityType.WOOD] == 3
        world.verify_invariant()
