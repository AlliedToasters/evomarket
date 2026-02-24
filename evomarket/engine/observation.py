"""Observation generation — structured per-agent views of world state."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from evomarket.core.types import CommodityType, Millicredits
from evomarket.engine.trading import (
    TradeStatus,
)

if TYPE_CHECKING:
    from evomarket.core.world import WorldState


# ---------------------------------------------------------------------------
# View models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreambleData:
    """Immutable game context included in every observation."""

    tick: int


@dataclass(frozen=True)
class AgentStateView:
    """An agent's own state as seen in observations."""

    location: str
    credits: Millicredits
    inventory: dict[CommodityType, int]
    age: int
    grace_ticks_remaining: int


@dataclass(frozen=True)
class NodeView:
    """Information about the agent's current node."""

    node_id: str
    name: str
    node_type: str
    adjacent_nodes: list[str]
    npc_prices: dict[CommodityType, Millicredits]
    resource_availability: dict[CommodityType, int]


@dataclass(frozen=True)
class AgentPublicView:
    """Public information about another agent at the same node."""

    agent_id: str
    display_name: str
    age: int


@dataclass(frozen=True)
class OrderView:
    """View of a posted order."""

    order_id: str
    poster_id: str
    side: str
    commodity: CommodityType
    quantity: int
    price_per_unit: Millicredits


@dataclass(frozen=True)
class MessageView:
    """View of a delivered message."""

    message_id: str
    sender_id: str
    text: str
    sent_tick: int


@dataclass(frozen=True)
class TradeProposalView:
    """View of an incoming trade proposal."""

    trade_id: str
    proposer_id: str
    offer_commodities: dict[CommodityType, int]
    offer_credits: Millicredits
    request_commodities: dict[CommodityType, int]
    request_credits: Millicredits


@dataclass(frozen=True)
class AgentObservation:
    """Complete observation for a single agent at a point in time."""

    preamble: PreambleData
    prompt_document: str
    agent_state: AgentStateView
    node_info: NodeView
    agents_present: list[AgentPublicView]
    posted_orders: list[OrderView]
    messages_received: list[MessageView]
    pending_proposals: list[TradeProposalView]
    own_orders: list[OrderView]
    own_pending_proposals: list[TradeProposalView]
    own_will: dict[str, float]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_observations(world: WorldState) -> dict[str, AgentObservation]:
    """Generate structured observations for all living agents."""
    observations: dict[str, AgentObservation] = {}

    preamble = PreambleData(tick=world.tick)

    for agent_id, agent in world.agents.items():
        if not agent.alive:
            continue

        node = world.nodes[agent.location]

        # Agent state view
        agent_state = AgentStateView(
            location=agent.location,
            credits=agent.credits,
            inventory=dict(agent.inventory),
            age=agent.age,
            grace_ticks_remaining=agent.grace_ticks_remaining,
        )

        # Node info with NPC prices and resource availability
        npc_prices: dict[CommodityType, Millicredits] = {}
        for commodity in node.npc_buys:
            npc_prices[commodity] = world.get_npc_price(agent.location, commodity)

        resource_availability: dict[CommodityType, int] = {}
        for commodity, stockpile in node.resource_stockpile.items():
            resource_availability[commodity] = math.floor(stockpile)

        node_info = NodeView(
            node_id=node.node_id,
            name=node.name,
            node_type=node.node_type.value,
            adjacent_nodes=list(node.adjacent_nodes),
            npc_prices=npc_prices,
            resource_availability=resource_availability,
        )

        # Other agents at the same node
        agents_present = [
            AgentPublicView(
                agent_id=a.agent_id,
                display_name=a.display_name,
                age=a.age,
            )
            for a in world.agents_at_node(agent.location)
            if a.agent_id != agent_id
        ]

        # Active orders at the node
        posted_orders = [
            _order_to_view(o) for o in world.orders_at_node(agent.location)
        ]

        # Messages delivered to this agent
        delivered = world.delivered_messages.get(agent_id, [])
        messages_received = [
            MessageView(
                message_id=m.message_id,
                sender_id=m.sender_id,
                text=m.text,
                sent_tick=m.sent_tick,
            )
            for m in delivered
        ]

        # Incoming trade proposals (agent is target)
        pending_proposals = [
            _proposal_to_view(p)
            for p in world.trade_proposals.values()
            if getattr(p, "target_id", None) == agent_id
            and getattr(p, "status", None) == TradeStatus.PENDING
        ]

        # Agent's own orders (all nodes, non-terminal)
        own_orders = [_order_to_view(o) for o in world.orders_for_agent(agent_id)]

        # Agent's own outgoing trade proposals
        own_pending_proposals = [
            _proposal_to_view(p)
            for p in world.trade_proposals.values()
            if getattr(p, "proposer_id", None) == agent_id
            and getattr(p, "status", None) == TradeStatus.PENDING
        ]

        observations[agent_id] = AgentObservation(
            preamble=preamble,
            prompt_document=agent.prompt_document,
            agent_state=agent_state,
            node_info=node_info,
            agents_present=agents_present,
            posted_orders=posted_orders,
            messages_received=messages_received,
            pending_proposals=pending_proposals,
            own_orders=own_orders,
            own_pending_proposals=own_pending_proposals,
            own_will=dict(agent.will),
        )

    return observations


def _order_to_view(order: object) -> OrderView:
    """Convert a PostedOrder to an OrderView."""
    return OrderView(
        order_id=order.order_id,
        poster_id=order.poster_id,
        side=order.side.value,
        commodity=order.commodity,
        quantity=order.quantity,
        price_per_unit=order.price_per_unit,
    )


def _proposal_to_view(proposal: object) -> TradeProposalView:
    """Convert a TradeProposal to a TradeProposalView."""
    return TradeProposalView(
        trade_id=proposal.trade_id,
        proposer_id=proposal.proposer_id,
        offer_commodities=dict(proposal.offer_commodities),
        offer_credits=proposal.offer_credits,
        request_commodities=dict(proposal.request_commodities),
        request_credits=proposal.request_credits,
    )
