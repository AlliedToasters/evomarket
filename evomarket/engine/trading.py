"""Order book, P2P trades, settlement, and trade history."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from evomarket.core.types import CommodityType, Millicredits

if TYPE_CHECKING:
    from evomarket.core.world import WorldState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BuySell(str, Enum):
    """Side of an order book order."""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    """Lifecycle status of a posted order."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class TradeStatus(str, Enum):
    """Lifecycle status of a P2P trade proposal."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class PostedOrder(BaseModel):
    """A public buy or sell order posted at a node."""

    model_config = ConfigDict(frozen=False)

    order_id: str
    poster_id: str
    node_id: str
    side: BuySell
    commodity: CommodityType
    quantity: int
    price_per_unit: Millicredits
    status: OrderStatus
    created_tick: int


class TradeProposal(BaseModel):
    """A direct trade proposal between two co-located agents."""

    model_config = ConfigDict(frozen=False)

    trade_id: str
    proposer_id: str
    target_id: str
    node_id: str
    offer_commodities: dict[CommodityType, int]
    offer_credits: Millicredits
    request_commodities: dict[CommodityType, int]
    request_credits: Millicredits
    status: TradeStatus
    created_tick: int

    @model_validator(mode="after")
    def _validate_non_empty(self) -> TradeProposal:
        has_offer = self.offer_credits > 0 or any(
            q > 0 for q in self.offer_commodities.values()
        )
        has_request = self.request_credits > 0 or any(
            q > 0 for q in self.request_commodities.values()
        )
        if not has_offer and not has_request:
            raise ValueError("Trade proposal must offer or request at least one item")
        return self


@dataclass
class TradeResult:
    """Result of a completed or failed trade attempt."""

    success: bool
    trade_type: Literal["order", "p2p"]
    buyer_id: str
    seller_id: str
    items_transferred: dict[CommodityType, int] = field(default_factory=dict)
    credits_transferred: Millicredits = 0
    failure_reason: str | None = None
    tick: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_order_id(world: WorldState) -> str:
    """Generate a deterministic order ID."""
    seq = world.next_order_seq
    world.next_order_seq = seq + 1
    return f"order_{world.tick}_{seq}"


def _next_trade_id(world: WorldState) -> str:
    """Generate a deterministic trade ID."""
    seq = world.next_order_seq
    world.next_order_seq = seq + 1
    return f"trade_{world.tick}_{seq}"


def _agent_has_commodities(
    world: WorldState, agent_id: str, commodities: dict[CommodityType, int]
) -> bool:
    """Check if agent has at least the specified commodity quantities."""
    agent = world.agents[agent_id]
    for commodity, qty in commodities.items():
        if qty > 0 and agent.inventory.get(commodity, 0) < qty:
            return False
    return True


def _agent_has_credits(world: WorldState, agent_id: str, amount: Millicredits) -> bool:
    """Check if agent has at least the specified credits."""
    return world.agents[agent_id].credits >= amount


def _transfer_commodities(
    world: WorldState,
    from_id: str,
    to_id: str,
    commodities: dict[CommodityType, int],
) -> None:
    """Transfer commodities between agents by mutating inventories."""
    from_agent = world.agents[from_id]
    to_agent = world.agents[to_id]
    for commodity, qty in commodities.items():
        if qty > 0:
            from_agent.inventory[commodity] = from_agent.inventory.get(commodity, 0) - qty
            to_agent.inventory[commodity] = to_agent.inventory.get(commodity, 0) + qty


def _orders_count_for_agent(world: WorldState, agent_id: str) -> int:
    """Count active + suspended orders for an agent."""
    return sum(
        1
        for o in world.order_book.values()
        if o.poster_id == agent_id
        and o.status in (OrderStatus.ACTIVE, OrderStatus.SUSPENDED)
    )


def _pending_proposals_count_for_agent(world: WorldState, agent_id: str) -> int:
    """Count pending proposals where agent is proposer."""
    return sum(
        1
        for p in world.trade_proposals.values()
        if p.proposer_id == agent_id and p.status == TradeStatus.PENDING
    )


def _record_trade(world: WorldState, result: TradeResult, node_id: str) -> None:
    """Record a successful trade result in node history."""
    if result.success:
        if node_id not in world.trade_history:
            world.trade_history[node_id] = []
        world.trade_history[node_id].append(result)


# ---------------------------------------------------------------------------
# Order Book Operations
# ---------------------------------------------------------------------------


def post_order(
    world: WorldState,
    agent_id: str,
    *,
    side: BuySell,
    commodity: CommodityType,
    quantity: int,
    price_per_unit: Millicredits,
) -> PostedOrder | None:
    """Post a buy or sell order at the agent's current node.

    Returns the created order, or None if validation fails.
    """
    agent = world.agents[agent_id]

    # Check order limit
    if _orders_count_for_agent(world, agent_id) >= world.config.max_open_orders:
        logger.warning(
            "Agent %s at order limit (%d), cannot post",
            agent_id,
            world.config.max_open_orders,
        )
        return None

    order = PostedOrder(
        order_id=_next_order_id(world),
        poster_id=agent_id,
        node_id=agent.location,
        side=side,
        commodity=commodity,
        quantity=quantity,
        price_per_unit=price_per_unit,
        status=OrderStatus.ACTIVE,
        created_tick=world.tick,
    )
    world.order_book[order.order_id] = order
    return order


def cancel_order(world: WorldState, agent_id: str, order_id: str) -> bool:
    """Cancel a posted order. Only the poster can cancel.

    Returns True if cancelled, False if rejected.
    """
    order = world.order_book.get(order_id)
    if order is None:
        return False
    if order.poster_id != agent_id:
        logger.warning("Agent %s cannot cancel order %s (not poster)", agent_id, order_id)
        return False
    if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
        return False
    order.status = OrderStatus.CANCELLED
    return True


def accept_order(world: WorldState, agent_id: str, order_id: str) -> TradeResult:
    """Accept (fill) a posted order.

    Validates co-location, order status, and both parties' ability to cover.
    """
    order = world.order_book.get(order_id)
    if order is None:
        return TradeResult(
            success=False,
            trade_type="order",
            buyer_id=agent_id,
            seller_id="",
            failure_reason="order not found",
            tick=world.tick,
        )

    acceptor = world.agents[agent_id]

    # Must be at same node
    if acceptor.location != order.node_id:
        return TradeResult(
            success=False,
            trade_type="order",
            buyer_id=agent_id,
            seller_id=order.poster_id,
            failure_reason="acceptor not at order node",
            tick=world.tick,
        )

    # Order must be ACTIVE
    if order.status != OrderStatus.ACTIVE:
        return TradeResult(
            success=False,
            trade_type="order",
            buyer_id=agent_id,
            seller_id=order.poster_id,
            failure_reason=f"order is {order.status.value}, not ACTIVE",
            tick=world.tick,
        )

    total_credits = order.price_per_unit * order.quantity
    items = {order.commodity: order.quantity}

    if order.side == BuySell.SELL:
        # Poster sells, acceptor buys
        seller_id = order.poster_id
        buyer_id = agent_id

        # Check poster has inventory
        if not _agent_has_commodities(world, seller_id, items):
            order.status = OrderStatus.CANCELLED
            return TradeResult(
                success=False,
                trade_type="order",
                buyer_id=buyer_id,
                seller_id=seller_id,
                failure_reason="poster cannot cover",
                tick=world.tick,
            )

        # Check acceptor has credits
        if not _agent_has_credits(world, buyer_id, total_credits):
            return TradeResult(
                success=False,
                trade_type="order",
                buyer_id=buyer_id,
                seller_id=seller_id,
                failure_reason="acceptor cannot cover",
                tick=world.tick,
            )
    else:
        # Poster buys, acceptor sells
        buyer_id = order.poster_id
        seller_id = agent_id

        # Check poster has credits
        if not _agent_has_credits(world, buyer_id, total_credits):
            order.status = OrderStatus.CANCELLED
            return TradeResult(
                success=False,
                trade_type="order",
                buyer_id=buyer_id,
                seller_id=seller_id,
                failure_reason="poster cannot cover",
                tick=world.tick,
            )

        # Check acceptor has inventory
        if not _agent_has_commodities(world, seller_id, items):
            return TradeResult(
                success=False,
                trade_type="order",
                buyer_id=buyer_id,
                seller_id=seller_id,
                failure_reason="acceptor cannot cover",
                tick=world.tick,
            )

    # Execute the trade
    _transfer_commodities(world, seller_id, buyer_id, items)
    world.transfer_credits(buyer_id, seller_id, total_credits)
    order.status = OrderStatus.FILLED

    result = TradeResult(
        success=True,
        trade_type="order",
        buyer_id=buyer_id,
        seller_id=seller_id,
        items_transferred=items,
        credits_transferred=total_credits,
        tick=world.tick,
    )
    _record_trade(world, result, order.node_id)
    world.verify_invariant()
    return result


def suspend_orders_for_agent(
    world: WorldState, agent_id: str, node_id: str
) -> None:
    """Suspend all ACTIVE orders for an agent at a node (called on departure)."""
    for order in world.order_book.values():
        if (
            order.poster_id == agent_id
            and order.node_id == node_id
            and order.status == OrderStatus.ACTIVE
        ):
            order.status = OrderStatus.SUSPENDED


def reactivate_orders_for_agent(
    world: WorldState, agent_id: str, node_id: str
) -> None:
    """Reactivate all SUSPENDED orders for an agent at a node (called on arrival)."""
    for order in world.order_book.values():
        if (
            order.poster_id == agent_id
            and order.node_id == node_id
            and order.status == OrderStatus.SUSPENDED
        ):
            order.status = OrderStatus.ACTIVE


# ---------------------------------------------------------------------------
# P2P Trade Operations
# ---------------------------------------------------------------------------


def propose_trade(
    world: WorldState,
    proposer_id: str,
    target_id: str,
    *,
    offer_commodities: dict[CommodityType, int] | None = None,
    offer_credits: Millicredits = 0,
    request_commodities: dict[CommodityType, int] | None = None,
    request_credits: Millicredits = 0,
) -> TradeProposal | None:
    """Propose a direct trade to a co-located agent.

    Returns the created proposal, or None if validation fails.
    """
    offer_comm = offer_commodities or {}
    request_comm = request_commodities or {}

    proposer = world.agents[proposer_id]
    target = world.agents[target_id]

    # Must be co-located
    if proposer.location != target.location:
        logger.warning(
            "Cannot propose trade: %s at %s, %s at %s",
            proposer_id,
            proposer.location,
            target_id,
            target.location,
        )
        return None

    # Proposer must have offered items
    if not _agent_has_commodities(world, proposer_id, offer_comm):
        logger.warning("Agent %s lacks offered commodities for trade", proposer_id)
        return None

    # Proposer must have offered credits
    if offer_credits > 0 and not _agent_has_credits(world, proposer_id, offer_credits):
        logger.warning("Agent %s lacks offered credits for trade", proposer_id)
        return None

    # Check pending proposal limit
    if (
        _pending_proposals_count_for_agent(world, proposer_id)
        >= world.config.max_pending_trades
    ):
        logger.warning(
            "Agent %s at pending trade limit (%d)",
            proposer_id,
            world.config.max_pending_trades,
        )
        return None

    # Validate non-empty (will also be checked by Pydantic)
    has_anything = (
        offer_credits > 0
        or request_credits > 0
        or any(q > 0 for q in offer_comm.values())
        or any(q > 0 for q in request_comm.values())
    )
    if not has_anything:
        logger.warning("Empty trade proposal from %s", proposer_id)
        return None

    proposal = TradeProposal(
        trade_id=_next_trade_id(world),
        proposer_id=proposer_id,
        target_id=target_id,
        node_id=proposer.location,
        offer_commodities=offer_comm,
        offer_credits=offer_credits,
        request_commodities=request_comm,
        request_credits=request_credits,
        status=TradeStatus.PENDING,
        created_tick=world.tick,
    )
    world.trade_proposals[proposal.trade_id] = proposal
    return proposal


def accept_trade(world: WorldState, agent_id: str, trade_id: str) -> TradeResult:
    """Accept a pending trade proposal. Only the target can accept."""
    proposal = world.trade_proposals.get(trade_id)
    if proposal is None:
        return TradeResult(
            success=False,
            trade_type="p2p",
            buyer_id=agent_id,
            seller_id="",
            failure_reason="proposal not found",
            tick=world.tick,
        )

    if proposal.target_id != agent_id:
        return TradeResult(
            success=False,
            trade_type="p2p",
            buyer_id=agent_id,
            seller_id=proposal.proposer_id,
            failure_reason="agent is not the target",
            tick=world.tick,
        )

    if proposal.status != TradeStatus.PENDING:
        return TradeResult(
            success=False,
            trade_type="p2p",
            buyer_id=agent_id,
            seller_id=proposal.proposer_id,
            failure_reason=f"proposal is {proposal.status.value}, not PENDING",
            tick=world.tick,
        )

    proposer = world.agents[proposal.proposer_id]
    target = world.agents[agent_id]

    # Must still be co-located
    if proposer.location != target.location:
        proposal.status = TradeStatus.INVALID
        return TradeResult(
            success=False,
            trade_type="p2p",
            buyer_id=agent_id,
            seller_id=proposal.proposer_id,
            failure_reason="agents no longer co-located",
            tick=world.tick,
        )

    # Verify proposer still has offered items/credits
    if not _agent_has_commodities(
        world, proposal.proposer_id, proposal.offer_commodities
    ):
        proposal.status = TradeStatus.INVALID
        return TradeResult(
            success=False,
            trade_type="p2p",
            buyer_id=agent_id,
            seller_id=proposal.proposer_id,
            failure_reason="proposer cannot cover offered commodities",
            tick=world.tick,
        )
    if proposal.offer_credits > 0 and not _agent_has_credits(
        world, proposal.proposer_id, proposal.offer_credits
    ):
        proposal.status = TradeStatus.INVALID
        return TradeResult(
            success=False,
            trade_type="p2p",
            buyer_id=agent_id,
            seller_id=proposal.proposer_id,
            failure_reason="proposer cannot cover offered credits",
            tick=world.tick,
        )

    # Verify target has requested items/credits
    if not _agent_has_commodities(world, agent_id, proposal.request_commodities):
        proposal.status = TradeStatus.INVALID
        return TradeResult(
            success=False,
            trade_type="p2p",
            buyer_id=agent_id,
            seller_id=proposal.proposer_id,
            failure_reason="target cannot cover requested commodities",
            tick=world.tick,
        )
    if proposal.request_credits > 0 and not _agent_has_credits(
        world, agent_id, proposal.request_credits
    ):
        proposal.status = TradeStatus.INVALID
        return TradeResult(
            success=False,
            trade_type="p2p",
            buyer_id=agent_id,
            seller_id=proposal.proposer_id,
            failure_reason="target cannot cover requested credits",
            tick=world.tick,
        )

    # Execute the trade
    # Proposer -> Target: offer_commodities + offer_credits
    _transfer_commodities(
        world, proposal.proposer_id, agent_id, proposal.offer_commodities
    )
    if proposal.offer_credits > 0:
        world.transfer_credits(proposal.proposer_id, agent_id, proposal.offer_credits)

    # Target -> Proposer: request_commodities + request_credits
    _transfer_commodities(
        world, agent_id, proposal.proposer_id, proposal.request_commodities
    )
    if proposal.request_credits > 0:
        world.transfer_credits(agent_id, proposal.proposer_id, proposal.request_credits)

    proposal.status = TradeStatus.ACCEPTED

    # Build result — for P2P, "buyer" is whoever pays more credits
    net_credits = proposal.offer_credits - proposal.request_credits
    if net_credits >= 0:
        buyer_id = proposal.proposer_id
        seller_id = agent_id
    else:
        buyer_id = agent_id
        seller_id = proposal.proposer_id

    # Combined items transferred
    all_items: dict[CommodityType, int] = {}
    for c, q in proposal.offer_commodities.items():
        if q > 0:
            all_items[c] = all_items.get(c, 0) + q
    for c, q in proposal.request_commodities.items():
        if q > 0:
            all_items[c] = all_items.get(c, 0) + q

    result = TradeResult(
        success=True,
        trade_type="p2p",
        buyer_id=buyer_id,
        seller_id=seller_id,
        items_transferred=all_items,
        credits_transferred=abs(net_credits),
        tick=world.tick,
    )
    _record_trade(world, result, proposal.node_id)
    world.verify_invariant()
    return result


def reject_trade(world: WorldState, agent_id: str, trade_id: str) -> bool:
    """Reject a pending trade proposal. Only the target can reject.

    Returns True if rejected, False if invalid operation.
    """
    proposal = world.trade_proposals.get(trade_id)
    if proposal is None:
        return False
    if proposal.target_id != agent_id:
        return False
    if proposal.status != TradeStatus.PENDING:
        return False
    proposal.status = TradeStatus.REJECTED
    return True


def expire_pending_trades(world: WorldState, max_age: int) -> list[str]:
    """Expire proposals older than max_age ticks. Returns expired trade IDs."""
    expired: list[str] = []
    for proposal in world.trade_proposals.values():
        if (
            proposal.status == TradeStatus.PENDING
            and world.tick - proposal.created_tick >= max_age
        ):
            proposal.status = TradeStatus.EXPIRED
            expired.append(proposal.trade_id)
    return expired


# ---------------------------------------------------------------------------
# Trade History
# ---------------------------------------------------------------------------


def get_trade_history(
    world: WorldState, node_id: str, limit: int = 50
) -> list[TradeResult]:
    """Return recent completed trades at a node, most recent first."""
    history = world.trade_history.get(node_id, [])
    # Most recent first (history is appended chronologically)
    return list(reversed(history[-limit:]))


# ---------------------------------------------------------------------------
# Death Cleanup
# ---------------------------------------------------------------------------


def cancel_all_orders_for_agent(world: WorldState, agent_id: str) -> None:
    """Cancel all orders and invalidate all proposals for a dead agent."""
    for order in world.order_book.values():
        if order.poster_id == agent_id and order.status in (
            OrderStatus.ACTIVE,
            OrderStatus.SUSPENDED,
        ):
            order.status = OrderStatus.CANCELLED

    for proposal in world.trade_proposals.values():
        if proposal.status == TradeStatus.PENDING and (
            proposal.proposer_id == agent_id or proposal.target_id == agent_id
        ):
            proposal.status = TradeStatus.INVALID
