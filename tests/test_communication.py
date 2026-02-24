"""Tests for the message passing system."""

from __future__ import annotations

import pytest

from evomarket.core.agent import Agent
from evomarket.core.types import CommodityType
from evomarket.core.world import WorldConfig, WorldState, generate_world
from evomarket.engine.communication import (
    Message,
    SendMessageAction,
    clear_messages_for_agent,
    deliver_pending_messages,
    get_message_history,
    get_messages_for_agent,
    send_message,
)


def _make_agent(agent_id: str, location: str, alive: bool = True) -> Agent:
    """Create a minimal agent for testing."""
    return Agent(
        agent_id=agent_id,
        display_name=agent_id,
        location=location,
        credits=30_000,
        inventory={CommodityType.IRON: 0, CommodityType.WOOD: 0},
        alive=alive,
        will={},
    )


@pytest.fixture
def simple_world() -> WorldState:
    """A minimal world with 2 agents at the same node."""

    config = WorldConfig(
        num_nodes=5,
        num_commodity_types=2,
        population_size=2,
        total_credit_supply=10_000_000,
        starting_credits=30_000,
    )
    # Build a minimal world by hand so we control agent locations
    w = generate_world(config, seed=42)
    # Clear agents and add our own at a known node
    node_id = next(iter(w.nodes))
    agent_credits = 0
    for a in w.agents.values():
        agent_credits += a.credits
    w.treasury += agent_credits
    w.agents.clear()

    a1 = _make_agent("agent_001", node_id)
    a2 = _make_agent("agent_002", node_id)
    w.agents["agent_001"] = a1
    w.agents["agent_002"] = a2
    w.treasury -= a1.credits + a2.credits
    return w


class TestMessageModel:
    """5.1 Test Message model creation and immutability."""

    def test_create_message(self) -> None:
        msg = Message(
            message_id="msg_0_0",
            sender_id="agent_001",
            recipient="agent_002",
            node_id="node_spawn",
            text="hello",
            sent_tick=0,
            delivered_tick=1,
        )
        assert msg.message_id == "msg_0_0"
        assert msg.sender_id == "agent_001"
        assert msg.recipient == "agent_002"
        assert msg.text == "hello"
        assert msg.sent_tick == 0
        assert msg.delivered_tick == 1
        assert msg.read is False

    def test_message_immutable(self) -> None:
        msg = Message(
            message_id="msg_0_0",
            sender_id="agent_001",
            recipient="agent_002",
            node_id="node_spawn",
            text="hello",
            sent_tick=0,
            delivered_tick=1,
        )
        with pytest.raises(Exception):  # ValidationError from frozen model
            msg.text = "changed"  # type: ignore[misc]


class TestSendPrivateMessage:
    """5.2 Test send_message — private."""

    def test_private_success(self, simple_world: WorldState) -> None:
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        msg = send_message(simple_world, action)
        assert msg is not None
        assert msg.sender_id == "agent_001"
        assert msg.recipient == "agent_002"
        assert msg.text == "hello"
        assert len(simple_world.pending_messages) == 1

    def test_reject_different_node(self, simple_world: WorldState) -> None:
        # Move agent_002 to a different node
        other_node = [
            n
            for n in simple_world.nodes
            if n != simple_world.agents["agent_001"].location
        ][0]
        simple_world.agents["agent_002"].location = other_node
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        msg = send_message(simple_world, action)
        assert msg is None
        assert len(simple_world.pending_messages) == 0

    def test_reject_dead_sender(self, simple_world: WorldState) -> None:
        simple_world.agents["agent_001"].alive = False
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        msg = send_message(simple_world, action)
        assert msg is None

    def test_reject_dead_recipient(self, simple_world: WorldState) -> None:
        simple_world.agents["agent_002"].alive = False
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        msg = send_message(simple_world, action)
        assert msg is None

    def test_text_truncation(self, simple_world: WorldState) -> None:
        long_text = "x" * 1000
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text=long_text
        )
        msg = send_message(simple_world, action)
        assert msg is not None
        assert len(msg.text) == simple_world.config.message_max_length


class TestSendBroadcastMessage:
    """5.3 Test send_message — broadcast."""

    def test_broadcast_to_multiple(self, simple_world: WorldState) -> None:
        # Add a third agent at the same node
        node_id = simple_world.agents["agent_001"].location
        a3 = _make_agent("agent_003", node_id)
        simple_world.agents["agent_003"] = a3
        simple_world.treasury -= a3.credits

        action = SendMessageAction(
            sender_id="agent_001", recipient="broadcast", text="hello all"
        )
        msg = send_message(simple_world, action)
        assert msg is not None
        # Two pending messages: one for agent_002, one for agent_003
        assert len(simple_world.pending_messages) == 2
        recipients = {m.recipient for m in simple_world.pending_messages}
        assert recipients == {"agent_002", "agent_003"}

    def test_broadcast_no_others(self, simple_world: WorldState) -> None:
        # Move agent_002 away
        other_node = [
            n
            for n in simple_world.nodes
            if n != simple_world.agents["agent_001"].location
        ][0]
        simple_world.agents["agent_002"].location = other_node
        action = SendMessageAction(
            sender_id="agent_001", recipient="broadcast", text="anyone?"
        )
        msg = send_message(simple_world, action)
        assert msg is None
        assert len(simple_world.pending_messages) == 0

    def test_broadcast_excludes_dead(self, simple_world: WorldState) -> None:
        # Add agent_003 (alive) and kill agent_002
        node_id = simple_world.agents["agent_001"].location
        a3 = _make_agent("agent_003", node_id)
        simple_world.agents["agent_003"] = a3
        simple_world.treasury -= a3.credits
        simple_world.agents["agent_002"].alive = False

        action = SendMessageAction(
            sender_id="agent_001", recipient="broadcast", text="hello"
        )
        msg = send_message(simple_world, action)
        assert msg is not None
        assert len(simple_world.pending_messages) == 1
        assert simple_world.pending_messages[0].recipient == "agent_003"


class TestDeliverPendingMessages:
    """5.4 Test deliver_pending_messages."""

    def test_standard_delivery(self, simple_world: WorldState) -> None:
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        send_message(simple_world, action)
        assert len(simple_world.pending_messages) == 1

        count = deliver_pending_messages(simple_world)
        assert count == 1
        assert len(simple_world.pending_messages) == 0
        assert "agent_002" in simple_world.delivered_messages
        assert len(simple_world.delivered_messages["agent_002"]) == 1

    def test_drop_to_dead(self, simple_world: WorldState) -> None:
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        send_message(simple_world, action)
        # Kill recipient before delivery
        simple_world.agents["agent_002"].alive = False
        count = deliver_pending_messages(simple_world)
        assert count == 0
        assert "agent_002" not in simple_world.delivered_messages

    def test_deliver_to_moved_agent(self, simple_world: WorldState) -> None:
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        send_message(simple_world, action)
        # Move recipient to a different node before delivery
        other_node = [
            n
            for n in simple_world.nodes
            if n != simple_world.agents["agent_002"].location
        ][0]
        simple_world.agents["agent_002"].location = other_node
        count = deliver_pending_messages(simple_world)
        assert count == 1
        assert len(simple_world.delivered_messages["agent_002"]) == 1


class TestOneTickLatency:
    """5.5 Test one-tick latency."""

    def test_not_available_same_tick(self, simple_world: WorldState) -> None:
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        send_message(simple_world, action)
        # Before delivery, agent_002 has no delivered messages
        msgs = get_messages_for_agent(simple_world, "agent_002")
        assert len(msgs) == 0

    def test_available_next_tick(self, simple_world: WorldState) -> None:
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        msg = send_message(simple_world, action)
        assert msg is not None
        assert msg.sent_tick == simple_world.tick
        assert msg.delivered_tick == simple_world.tick + 1

        # Simulate next tick: deliver
        deliver_pending_messages(simple_world)
        msgs = get_messages_for_agent(simple_world, "agent_002")
        assert len(msgs) == 1
        assert msgs[0].text == "hello"


class TestGetMessagesForAgent:
    """5.6 Test get_messages_for_agent."""

    def test_with_messages(self, simple_world: WorldState) -> None:
        for i in range(3):
            action = SendMessageAction(
                sender_id="agent_001", recipient="agent_002", text=f"msg {i}"
            )
            send_message(simple_world, action)
        deliver_pending_messages(simple_world)
        msgs = get_messages_for_agent(simple_world, "agent_002")
        assert len(msgs) == 3
        # Verify ordering by message_id
        ids = [m.message_id for m in msgs]
        assert ids == sorted(ids)

    def test_empty_list(self, simple_world: WorldState) -> None:
        msgs = get_messages_for_agent(simple_world, "agent_002")
        assert msgs == []


class TestBroadcastHistory:
    """5.7 Test broadcast history — query, bounded by limit."""

    def test_query_broadcast_history(self, simple_world: WorldState) -> None:
        for i in range(5):
            action = SendMessageAction(
                sender_id="agent_001", recipient="broadcast", text=f"broadcast {i}"
            )
            send_message(simple_world, action)

        node_id = simple_world.agents["agent_001"].location
        history = get_message_history(simple_world, node_id)
        assert len(history) == 5
        # Most recent first
        assert history[0].text == "broadcast 4"
        assert history[-1].text == "broadcast 0"

    def test_history_bounded_by_limit(self, simple_world: WorldState) -> None:
        limit = simple_world.config.broadcast_history_limit  # 20
        for i in range(limit + 5):
            action = SendMessageAction(
                sender_id="agent_001", recipient="broadcast", text=f"msg {i}"
            )
            send_message(simple_world, action)

        node_id = simple_world.agents["agent_001"].location
        history = get_message_history(simple_world, node_id)
        assert len(history) == limit
        # Most recent message should be the last one sent
        assert history[0].text == f"msg {limit + 4}"


class TestPrivateMessagePruning:
    """5.8 Test private message history pruning."""

    def test_prune_old_messages(self, simple_world: WorldState) -> None:
        limit = simple_world.config.private_message_history_limit  # 50
        for i in range(limit + 10):
            action = SendMessageAction(
                sender_id="agent_001", recipient="agent_002", text=f"msg {i}"
            )
            send_message(simple_world, action)
        deliver_pending_messages(simple_world)
        msgs = get_messages_for_agent(simple_world, "agent_002")
        assert len(msgs) == limit
        # Should have the most recent messages
        assert msgs[-1].text == f"msg {limit + 9}"


class TestClearMessagesForAgent:
    """5.9 Test clear_messages_for_agent."""

    def test_clear_from_dead_sender(self, simple_world: WorldState) -> None:
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        send_message(simple_world, action)
        assert len(simple_world.pending_messages) == 1
        clear_messages_for_agent(simple_world, "agent_001")
        assert len(simple_world.pending_messages) == 0

    def test_clear_to_dead_recipient(self, simple_world: WorldState) -> None:
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        send_message(simple_world, action)
        clear_messages_for_agent(simple_world, "agent_002")
        assert len(simple_world.pending_messages) == 0

    def test_delivered_messages_remain(self, simple_world: WorldState) -> None:
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        send_message(simple_world, action)
        deliver_pending_messages(simple_world)
        assert len(simple_world.delivered_messages.get("agent_002", [])) == 1
        # Now agent_001 dies — already-delivered messages should remain
        clear_messages_for_agent(simple_world, "agent_001")
        assert len(simple_world.delivered_messages.get("agent_002", [])) == 1


class TestDeterministicMessageIds:
    """5.10 Test deterministic message IDs."""

    def test_sequential_ids_within_tick(self, simple_world: WorldState) -> None:
        simple_world.tick = 5
        for i in range(3):
            action = SendMessageAction(
                sender_id="agent_001", recipient="agent_002", text=f"msg {i}"
            )
            send_message(simple_world, action)
        ids = [m.message_id for m in simple_world.pending_messages]
        assert ids == ["msg_5_0", "msg_5_1", "msg_5_2"]

    def test_seq_resets_after_delivery(self, simple_world: WorldState) -> None:
        simple_world.tick = 0
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="first"
        )
        send_message(simple_world, action)
        deliver_pending_messages(simple_world)
        # Seq should reset to 0 after delivery
        assert simple_world.next_message_seq == 0

        simple_world.tick = 1
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="second"
        )
        msg = send_message(simple_world, action)
        assert msg is not None
        assert msg.message_id == "msg_1_0"


class TestWorldStateSerialization:
    """5.11 Test WorldState serialization round-trip with message queue state."""

    def test_round_trip_with_messages(self, simple_world: WorldState) -> None:
        # Send a message and deliver it
        action = SendMessageAction(
            sender_id="agent_001", recipient="agent_002", text="hello"
        )
        send_message(simple_world, action)

        # Send a broadcast (creates broadcast_history)
        action2 = SendMessageAction(
            sender_id="agent_001", recipient="broadcast", text="broadcast msg"
        )
        send_message(simple_world, action2)

        # Deliver pending
        deliver_pending_messages(simple_world)

        # Add another pending message
        action3 = SendMessageAction(
            sender_id="agent_002", recipient="agent_001", text="reply"
        )
        send_message(simple_world, action3)

        # Serialize and deserialize
        data = simple_world.to_json()
        restored = WorldState.from_json(data)

        # Verify message queue state
        assert len(restored.pending_messages) == len(simple_world.pending_messages)
        assert restored.pending_messages[0].text == "reply"
        assert len(restored.delivered_messages) == len(simple_world.delivered_messages)
        assert restored.next_message_seq == simple_world.next_message_seq

        # Verify broadcast history
        node_id = simple_world.agents["agent_001"].location
        assert len(restored.broadcast_history.get(node_id, [])) == len(
            simple_world.broadcast_history.get(node_id, [])
        )

        # Verify invariant still holds
        restored.verify_invariant()
