"""Message passing system — agent-to-agent and broadcast messages.

Messages have one-tick delivery latency, node-local scope, and bounded history.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from evomarket.core.world import WorldState


class Message(BaseModel):
    """An immutable message between agents."""

    model_config = ConfigDict(frozen=True)

    message_id: str
    sender_id: str
    recipient: str
    node_id: str
    text: str
    sent_tick: int
    delivered_tick: int
    read: bool = False


class SendMessageAction(BaseModel):
    """Action for an agent to send a message."""

    model_config = ConfigDict(frozen=True)

    sender_id: str
    recipient: str  # agent_id or "broadcast"
    text: str


def send_message(world: WorldState, action: SendMessageAction) -> Message | None:
    """Send a message from one agent to others at the same node.

    Returns the Message (or first of broadcast fan-out) on success, None on failure.
    For broadcasts, creates one pending message per recipient at the node.
    """
    sender = world.agents.get(action.sender_id)
    if sender is None or not sender.alive:
        return None

    node_id = sender.location
    text = action.text[: world.config.message_max_length]

    if action.recipient == "broadcast":
        recipients = [
            a.agent_id
            for a in world.agents_at_node(node_id)
            if a.agent_id != action.sender_id
        ]
        if not recipients:
            return None
        first: Message | None = None
        for recipient_id in recipients:
            msg = _create_message(world, action.sender_id, recipient_id, node_id, text)
            world.pending_messages.append(msg)
            # Track in broadcast history
            history = world.broadcast_history.setdefault(node_id, [])
            history.append(msg)
            if len(history) > world.config.broadcast_history_limit:
                del history[: len(history) - world.config.broadcast_history_limit]
            if first is None:
                first = msg
        return first
    else:
        # Private message — verify recipient is co-located and alive
        recipient = world.agents.get(action.recipient)
        if recipient is None or not recipient.alive:
            return None
        if recipient.location != node_id:
            return None
        msg = _create_message(world, action.sender_id, action.recipient, node_id, text)
        world.pending_messages.append(msg)
        return msg


def _create_message(
    world: WorldState,
    sender_id: str,
    recipient_id: str,
    node_id: str,
    text: str,
) -> Message:
    """Create a Message with a deterministic ID."""
    seq = world.next_message_seq
    world.next_message_seq += 1
    return Message(
        message_id=f"msg_{world.tick}_{seq}",
        sender_id=sender_id,
        recipient=recipient_id,
        node_id=node_id,
        text=text,
        sent_tick=world.tick,
        delivered_tick=world.tick + 1,
    )


def deliver_pending_messages(world: WorldState) -> int:
    """Deliver all pending messages to recipients. Called during RECEIVE phase.

    Messages to dead agents are dropped. Returns the count of messages delivered.
    """
    delivered_count = 0
    for msg in world.pending_messages:
        recipient = world.agents.get(msg.recipient)
        if recipient is None or not recipient.alive:
            continue
        inbox = world.delivered_messages.setdefault(msg.recipient, [])
        inbox.append(msg)
        delivered_count += 1
        # Prune private history
        limit = world.config.private_message_history_limit
        if len(inbox) > limit:
            del inbox[: len(inbox) - limit]
    world.pending_messages.clear()
    world.next_message_seq = 0
    return delivered_count


def get_messages_for_agent(world: WorldState, agent_id: str) -> list[Message]:
    """Return all delivered messages for an agent, ordered by message_id."""
    messages = world.delivered_messages.get(agent_id, [])
    return sorted(messages, key=lambda m: m.message_id)


def get_message_history(
    world: WorldState, node_id: str, limit: int | None = None
) -> list[Message]:
    """Return recent broadcast messages at a node, most recent first."""
    history = world.broadcast_history.get(node_id, [])
    result = list(reversed(history))
    if limit is not None:
        result = result[:limit]
    return result


def clear_messages_for_agent(world: WorldState, agent_id: str) -> None:
    """Remove pending messages from and to a dead agent. Called during DEATH phase."""
    world.pending_messages = [
        msg
        for msg in world.pending_messages
        if msg.sender_id != agent_id and msg.recipient != agent_id
    ]
