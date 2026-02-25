"""Observation generation — structured per-agent views of world state."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from evomarket.core.types import CommodityType, Millicredits, NodeType
from evomarket.engine.trading import (
    BuySell,
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
class AdjacentNodeInfo:
    """Minimal info about an adjacent node to help with navigation."""

    node_id: str
    node_type: str


@dataclass(frozen=True)
class NodeView:
    """Information about the agent's current node."""

    node_id: str
    name: str
    node_type: str
    adjacent_nodes: list[str]
    adjacent_node_info: list[AdjacentNodeInfo]
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
class SellableItem:
    """A commodity the agent can sell to an NPC at the current node."""

    commodity: CommodityType
    quantity_held: int
    npc_price: Millicredits


@dataclass(frozen=True)
class FillableOrder:
    """An order at the current node the agent can fill."""

    order_id: str
    poster_id: str
    side: str
    commodity: CommodityType
    quantity: int
    price_per_unit: Millicredits


@dataclass(frozen=True)
class MarketPriceView:
    """Prices at a trade hub, visible to all agents."""

    node_id: str
    node_name: str
    prices: dict[CommodityType, Millicredits]


@dataclass(frozen=True)
class ActionAvailability:
    """Pre-computed action availability for an agent."""

    can_move: bool
    adjacent_nodes: list[str]
    can_harvest: bool
    harvestable_resources: dict[CommodityType, int]
    can_sell_to_npc: bool
    sellable_items: list[SellableItem]
    can_buy_from_npc: bool
    can_post_sell_order: bool
    post_sell_inventory: dict[CommodityType, int]
    can_post_buy_order: bool
    fillable_orders: list[FillableOrder]
    can_propose_trade: bool
    tradeable_agents: list[str]
    acceptable_trades: list[str]
    can_inspect: bool


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
    action_availability: ActionAvailability | None = None
    market_prices: list[MarketPriceView] | None = None


# ---------------------------------------------------------------------------
# Action availability computation
# ---------------------------------------------------------------------------


def _compute_action_availability(
    agent_id: str,
    world: WorldState,
) -> ActionAvailability:
    """Compute which actions are available to an agent.

    Predicates mirror the canonical validators in engine/actions.py.
    """
    agent = world.agents[agent_id]
    node = world.nodes[agent.location]
    inv = {c: q for c, q in agent.inventory.items() if q > 0}

    # Move: adjacent nodes exist
    adjacent_nodes = list(node.adjacent_nodes)
    can_move = len(adjacent_nodes) > 0

    # Harvest: RESOURCE node with floor(stockpile) >= 1
    harvestable_resources: dict[CommodityType, int] = {}
    if node.node_type == NodeType.RESOURCE:
        for commodity, stockpile in node.resource_stockpile.items():
            floored = math.floor(stockpile)
            if floored >= 1:
                harvestable_resources[commodity] = floored
    can_harvest = bool(harvestable_resources)

    # NPC sell: agent has inventory matching node's npc_buys
    sellable_items: list[SellableItem] = []
    if inv and node.npc_buys:
        for commodity, qty in inv.items():
            if commodity in node.npc_buys:
                npc_price = world.get_npc_price(node.node_id, commodity)
                sellable_items.append(
                    SellableItem(
                        commodity=commodity,
                        quantity_held=qty,
                        npc_price=npc_price,
                    )
                )
    can_sell_to_npc = bool(sellable_items)

    # NPC buy: agent has credits and node has npc_buys
    can_buy_from_npc = bool(node.npc_buys and agent.credits > 0)

    # Post order: under max_open_orders limit, split by sell (needs inventory) / buy (needs credits)
    agent_order_count = len(world.orders_for_agent(agent_id))
    under_order_limit = agent_order_count < world.config.max_open_orders
    can_post_sell_order = under_order_limit and bool(inv)
    post_sell_inventory = dict(inv) if can_post_sell_order else {}
    can_post_buy_order = under_order_limit and agent.credits > 0

    # Fillable orders: orders at node the agent can fill, excluding own
    fillable_orders: list[FillableOrder] = []
    for order in world.orders_at_node(node.node_id):
        poster_id = getattr(order, "poster_id", None)
        if poster_id == agent_id:
            continue
        side = getattr(order, "side", None)
        commodity = getattr(order, "commodity", None)
        quantity = getattr(order, "quantity", 0)
        price_per_unit = getattr(order, "price_per_unit", 0)

        if side == BuySell.SELL:
            # Agent needs credits to buy
            cost = price_per_unit * quantity
            if agent.credits >= cost:
                fillable_orders.append(
                    FillableOrder(
                        order_id=getattr(order, "order_id", ""),
                        poster_id=poster_id,
                        side="sell",
                        commodity=commodity,
                        quantity=quantity,
                        price_per_unit=price_per_unit,
                    )
                )
        elif side == BuySell.BUY:
            # Agent needs inventory to sell
            agent_qty = inv.get(commodity, 0)
            if agent_qty >= quantity:
                fillable_orders.append(
                    FillableOrder(
                        order_id=getattr(order, "order_id", ""),
                        poster_id=poster_id,
                        side="buy",
                        commodity=commodity,
                        quantity=quantity,
                        price_per_unit=price_per_unit,
                    )
                )

    # Propose trade: other agents present AND under max_pending_trades
    other_agents = [
        a for a in world.agents_at_node(node.node_id) if a.agent_id != agent_id
    ]
    tradeable_agents = [a.agent_id for a in other_agents]
    trade_count = len(world.pending_proposals_for_agent(agent_id))
    can_propose_trade = (
        bool(tradeable_agents) and trade_count < world.config.max_pending_trades
    )

    # Acceptable trades: pending proposals where agent has requested items
    acceptable_trades: list[str] = []
    for proposal in world.trade_proposals.values():
        if getattr(proposal, "target_id", None) != agent_id:
            continue
        if getattr(proposal, "status", None) != TradeStatus.PENDING:
            continue
        request_commodities = getattr(proposal, "request_commodities", {})
        request_credits = getattr(proposal, "request_credits", 0)
        can_accept = True
        if request_credits > 0 and agent.credits < request_credits:
            can_accept = False
        if can_accept:
            for commodity, qty in request_commodities.items():
                if agent.inventory.get(commodity, 0) < qty:
                    can_accept = False
                    break
        if can_accept:
            acceptable_trades.append(getattr(proposal, "trade_id", ""))

    # Inspect: other agents present
    can_inspect = bool(tradeable_agents)

    return ActionAvailability(
        can_move=can_move,
        adjacent_nodes=adjacent_nodes,
        can_harvest=can_harvest,
        harvestable_resources=harvestable_resources,
        can_sell_to_npc=can_sell_to_npc,
        sellable_items=sellable_items,
        can_buy_from_npc=can_buy_from_npc,
        can_post_sell_order=can_post_sell_order,
        post_sell_inventory=post_sell_inventory,
        can_post_buy_order=can_post_buy_order,
        fillable_orders=fillable_orders,
        can_propose_trade=can_propose_trade,
        tradeable_agents=tradeable_agents,
        acceptable_trades=acceptable_trades,
        can_inspect=can_inspect,
    )


# ---------------------------------------------------------------------------
# Market prices (global visibility)
# ---------------------------------------------------------------------------


def _compute_market_prices(world: WorldState) -> list[MarketPriceView]:
    """Compute NPC buy prices at every TRADE_HUB node (once per tick)."""
    views: list[MarketPriceView] = []
    for node in world.nodes.values():
        if node.node_type != NodeType.TRADE_HUB:
            continue
        prices: dict[CommodityType, Millicredits] = {}
        for commodity in node.npc_buys:
            prices[commodity] = world.get_npc_price(node.node_id, commodity)
        views.append(
            MarketPriceView(
                node_id=node.node_id,
                node_name=node.name,
                prices=prices,
            )
        )
    return views


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_observations(world: WorldState) -> dict[str, AgentObservation]:
    """Generate structured observations for all living agents."""
    observations: dict[str, AgentObservation] = {}

    preamble = PreambleData(tick=world.tick)
    market_prices = _compute_market_prices(world)

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

        # Build adjacent node info with types
        adjacent_info = [
            AdjacentNodeInfo(
                node_id=adj_id,
                node_type=world.nodes[adj_id].node_type.value,
            )
            for adj_id in node.adjacent_nodes
            if adj_id in world.nodes
        ]

        node_info = NodeView(
            node_id=node.node_id,
            name=node.name,
            node_type=node.node_type.value,
            adjacent_nodes=list(node.adjacent_nodes),
            adjacent_node_info=adjacent_info,
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

        action_availability = _compute_action_availability(agent_id, world)

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
            action_availability=action_availability,
            market_prices=market_prices,
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
