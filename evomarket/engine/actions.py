"""Action types, validation, and resolution for the EvoMarket game engine.

Delegates to existing subsystem modules for trading, communication,
economy, and inheritance operations.
"""

from __future__ import annotations

import logging
import math
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator, field_validator

from evomarket.core.agent import Agent
from evomarket.core.types import CommodityType, Millicredits, NodeType
from evomarket.core.world import WorldState
from evomarket.engine.communication import (
    SendMessageAction as CommSendMessageAction,
    send_message,
)
from evomarket.engine.economy import process_npc_sell
from evomarket.engine.inheritance import update_will
from evomarket.engine.trading import (
    BuySell,
    accept_order,
    accept_trade,
    post_order,
    propose_trade,
    suspend_orders_for_agent,
    reactivate_orders_for_agent,
)

logger = logging.getLogger(__name__)

# Valid keys for trade item dicts: commodity names + "credits"
_VALID_TRADE_KEYS = {ct.value for ct in CommodityType} | {"credits"}


# ============================================================================
# Action Models
# ============================================================================


class BaseAction(BaseModel):
    """Base class for all agent actions."""

    model_config = ConfigDict(frozen=True)

    action_type: str


class MoveAction(BaseAction):
    """Move to an adjacent node."""

    action_type: Literal["move"] = "move"
    target_node: str


class HarvestAction(BaseAction):
    """Gather resources at the current node."""

    action_type: Literal["harvest"] = "harvest"


class PostOrderAction(BaseAction):
    """Post a buy or sell order at the current node."""

    action_type: Literal["post_order"] = "post_order"
    side: Literal["buy", "sell"]
    commodity: CommodityType
    quantity: int
    price: Millicredits

    @field_validator("quantity")
    @classmethod
    def _validate_quantity(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"Quantity must be positive, got {v}")
        return v

    @field_validator("price")
    @classmethod
    def _validate_price(cls, v: Millicredits) -> Millicredits:
        if v <= 0:
            raise ValueError(f"Price must be positive, got {v}")
        return v


class AcceptOrderAction(BaseAction):
    """Accept an existing order at the current node."""

    action_type: Literal["accept_order"] = "accept_order"
    order_id: str


class ProposeTradeAction(BaseAction):
    """Propose a direct trade with another agent at the same node."""

    action_type: Literal["propose_trade"] = "propose_trade"
    target_agent: str
    offer: dict[str, int]
    request: dict[str, int]

    @field_validator("offer", "request")
    @classmethod
    def _validate_trade_items(cls, v: dict[str, int]) -> dict[str, int]:
        for key, qty in v.items():
            if key not in _VALID_TRADE_KEYS:
                raise ValueError(
                    f"Invalid trade item key: {key!r}. "
                    f"Must be a CommodityType value or 'credits'"
                )
            if qty <= 0:
                raise ValueError(
                    f"Trade item quantity must be positive, got {qty} for {key}"
                )
        return v


class AcceptTradeAction(BaseAction):
    """Accept a pending trade proposal."""

    action_type: Literal["accept_trade"] = "accept_trade"
    trade_id: str


class SendMessageAction(BaseAction):
    """Send a message to another agent or broadcast to the current node."""

    action_type: Literal["send_message"] = "send_message"
    target: str
    text: str


class UpdateWillAction(BaseAction):
    """Update the agent's will (inheritance distribution)."""

    action_type: Literal["update_will"] = "update_will"
    distribution: dict[str, float]

    @field_validator("distribution")
    @classmethod
    def _validate_distribution(cls, v: dict[str, float]) -> dict[str, float]:
        for agent_id, pct in v.items():
            if pct < 0:
                raise ValueError(
                    f"Will percentage for {agent_id} must be non-negative, got {pct}"
                )
        total = sum(v.values())
        if total > 1.0 + 1e-9:
            raise ValueError(f"Will percentages sum to {total}, must be ≤ 1.0")
        return v


class InspectAction(BaseAction):
    """Inspect another agent at the same node."""

    action_type: Literal["inspect"] = "inspect"
    target_agent: str


class IdleAction(BaseAction):
    """Do nothing this tick."""

    action_type: Literal["idle"] = "idle"


# Discriminated union of all action types
Action = Annotated[
    Union[
        MoveAction,
        HarvestAction,
        PostOrderAction,
        AcceptOrderAction,
        ProposeTradeAction,
        AcceptTradeAction,
        SendMessageAction,
        UpdateWillAction,
        InspectAction,
        IdleAction,
    ],
    Discriminator("action_type"),
]


# ============================================================================
# Supporting Models
# ============================================================================


class AgentTurnResult(BaseModel):
    """The result of an agent's decision for a single tick."""

    action: Action
    scratchpad_update: str | None = None


class ActionResult(BaseModel):
    """The outcome of resolving a single agent's action."""

    agent_id: str
    action: Action
    success: bool
    detail: str


# ============================================================================
# Validation
# ============================================================================


def validate_action(agent_id: str, action: Action, world: WorldState) -> Action:
    """Validate an action against current world state.

    Returns the action unchanged if valid, or IdleAction if invalid.
    Invalid actions are logged as warnings.
    """
    agent = world.agents.get(agent_id)
    if agent is None or not agent.alive:
        logger.warning(
            "validate_action: agent %s not found or dead, %s → idle",
            agent_id,
            action.action_type,
        )
        return IdleAction()

    match action.action_type:
        case "idle":
            return action
        case "move":
            return _validate_move(agent_id, action, world, agent)  # type: ignore[arg-type]
        case "harvest":
            return _validate_harvest(agent_id, action, world, agent)
        case "post_order":
            return _validate_post_order(agent_id, action, world, agent)  # type: ignore[arg-type]
        case "accept_order":
            return _validate_accept_order(agent_id, action, world, agent)  # type: ignore[arg-type]
        case "propose_trade":
            return _validate_propose_trade(agent_id, action, world, agent)  # type: ignore[arg-type]
        case "accept_trade":
            return _validate_accept_trade(agent_id, action, world, agent)  # type: ignore[arg-type]
        case "send_message":
            return _validate_send_message(agent_id, action, world, agent)  # type: ignore[arg-type]
        case "update_will":
            return _validate_update_will(agent_id, action, world, agent)  # type: ignore[arg-type]
        case "inspect":
            return _validate_inspect(agent_id, action, world, agent)  # type: ignore[arg-type]

    logger.warning(
        "validate_action: unknown action type %s for agent %s → idle",
        action.action_type,
        agent_id,
    )
    return IdleAction()


def _invalid(agent_id: str, action_type: str, reason: str) -> IdleAction:
    """Log a warning and return IdleAction for an invalid action."""
    logger.warning(
        "validate_action: agent %s %s invalid: %s → idle",
        agent_id,
        action_type,
        reason,
    )
    return IdleAction()


def _validate_move(
    agent_id: str, action: MoveAction, world: WorldState, agent: Agent
) -> Action:
    if action.target_node not in world.nodes:
        return _invalid(
            agent_id, "move", f"target node {action.target_node} does not exist"
        )
    if action.target_node not in world.adjacent_nodes(agent.location):
        return _invalid(
            agent_id,
            "move",
            f"target node {action.target_node} not adjacent to {agent.location}",
        )
    return action


def _validate_harvest(
    agent_id: str, action: HarvestAction, world: WorldState, agent: Agent
) -> Action:
    node = world.nodes[agent.location]
    if node.node_type != NodeType.RESOURCE:
        return _invalid(
            agent_id,
            "harvest",
            f"node {agent.location} is {node.node_type.value}, not RESOURCE",
        )
    if not any(math.floor(qty) >= 1 for qty in node.resource_stockpile.values()):
        return _invalid(
            agent_id, "harvest", f"no harvestable resources at {agent.location}"
        )
    return action


def _validate_post_order(
    agent_id: str, action: PostOrderAction, world: WorldState, agent: Agent
) -> Action:
    # Use trading module's order count via WorldState query
    agent_order_count = len(world.orders_for_agent(agent_id))
    if agent_order_count >= world.config.max_open_orders:
        return _invalid(
            agent_id,
            "post_order",
            f"at max open orders ({world.config.max_open_orders})",
        )

    if action.side == "buy":
        total_cost = action.quantity * action.price
        if agent.credits < total_cost:
            return _invalid(
                agent_id,
                "post_order",
                f"insufficient credits for buy: has {agent.credits}, needs {total_cost}",
            )
    else:  # sell
        current_qty = agent.inventory.get(action.commodity, 0)
        if current_qty < action.quantity:
            return _invalid(
                agent_id,
                "post_order",
                f"insufficient {action.commodity.value}: has {current_qty}, needs {action.quantity}",
            )

    return action


def _validate_accept_order(
    agent_id: str, action: AcceptOrderAction, world: WorldState, agent: Agent
) -> Action:
    order = world.order_book.get(action.order_id)
    if order is None:
        return _invalid(
            agent_id, "accept_order", f"order {action.order_id} does not exist"
        )
    if getattr(order, "node_id", None) != agent.location:
        return _invalid(
            agent_id,
            "accept_order",
            f"order {action.order_id} at {getattr(order, 'node_id', '?')}, agent at {agent.location}",
        )

    from evomarket.engine.trading import OrderStatus

    if getattr(order, "status", None) != OrderStatus.ACTIVE:
        return _invalid(
            agent_id,
            "accept_order",
            f"order {action.order_id} is not active",
        )

    side = getattr(order, "side", None)
    if side == BuySell.SELL:
        # Acceptor is buying: needs credits
        total_cost = getattr(order, "quantity", 0) * getattr(order, "price_per_unit", 0)
        if agent.credits < total_cost:
            return _invalid(
                agent_id,
                "accept_order",
                f"insufficient credits to buy: has {agent.credits}, needs {total_cost}",
            )
    elif side == BuySell.BUY:
        # Acceptor is selling: needs commodity
        commodity = getattr(order, "commodity", None)
        quantity = getattr(order, "quantity", 0)
        current_qty = agent.inventory.get(commodity, 0)
        if current_qty < quantity:
            return _invalid(
                agent_id,
                "accept_order",
                f"insufficient {commodity}: has {current_qty}, needs {quantity}",
            )

    return action


def _validate_propose_trade(
    agent_id: str, action: ProposeTradeAction, world: WorldState, agent: Agent
) -> Action:
    if action.target_agent == agent_id:
        return _invalid(agent_id, "propose_trade", "cannot trade with self")

    target = world.agents.get(action.target_agent)
    if target is None or not target.alive:
        return _invalid(
            agent_id,
            "propose_trade",
            f"target agent {action.target_agent} not found or dead",
        )

    if target.location != agent.location:
        return _invalid(
            agent_id,
            "propose_trade",
            f"target agent {action.target_agent} at {target.location}, not at {agent.location}",
        )

    trade_count = len(world.pending_proposals_for_agent(agent_id))
    if trade_count >= world.config.max_pending_trades:
        return _invalid(
            agent_id,
            "propose_trade",
            f"at max pending trades ({world.config.max_pending_trades})",
        )

    for key, qty in action.offer.items():
        if key == "credits":
            if agent.credits < qty:
                return _invalid(
                    agent_id,
                    "propose_trade",
                    f"insufficient credits: has {agent.credits}, offering {qty}",
                )
        else:
            commodity = CommodityType(key)
            current = agent.inventory.get(commodity, 0)
            if current < qty:
                return _invalid(
                    agent_id,
                    "propose_trade",
                    f"insufficient {key}: has {current}, offering {qty}",
                )

    return action


def _validate_accept_trade(
    agent_id: str, action: AcceptTradeAction, world: WorldState, agent: Agent
) -> Action:
    proposal = world.trade_proposals.get(action.trade_id)
    if proposal is None:
        return _invalid(
            agent_id, "accept_trade", f"trade {action.trade_id} does not exist"
        )

    from evomarket.engine.trading import TradeStatus

    if getattr(proposal, "status", None) != TradeStatus.PENDING:
        return _invalid(
            agent_id, "accept_trade", f"trade {action.trade_id} is not pending"
        )

    if getattr(proposal, "target_id", None) != agent_id:
        return _invalid(
            agent_id,
            "accept_trade",
            f"trade {action.trade_id} is not pending for this agent",
        )

    # Check acceptor has the requested items
    request_commodities = getattr(proposal, "request_commodities", {})
    request_credits = getattr(proposal, "request_credits", 0)

    if request_credits > 0 and agent.credits < request_credits:
        return _invalid(
            agent_id,
            "accept_trade",
            f"insufficient credits: has {agent.credits}, needs {request_credits}",
        )

    for commodity, qty in request_commodities.items():
        current = agent.inventory.get(commodity, 0)
        if current < qty:
            return _invalid(
                agent_id,
                "accept_trade",
                f"insufficient {commodity.value}: has {current}, needs {qty}",
            )

    return action


def _validate_send_message(
    agent_id: str, action: SendMessageAction, world: WorldState, agent: Agent
) -> Action:
    if action.target == "all" or action.target == "broadcast":
        return action

    target = world.agents.get(action.target)
    if target is None or not target.alive:
        return _invalid(
            agent_id, "send_message", f"target agent {action.target} not found or dead"
        )
    if target.location != agent.location:
        return _invalid(
            agent_id,
            "send_message",
            f"target agent {action.target} at {target.location}, not at {agent.location}",
        )
    return action


def _validate_update_will(
    agent_id: str, action: UpdateWillAction, world: WorldState, agent: Agent
) -> Action:
    for beneficiary_id in action.distribution:
        if beneficiary_id not in world.agents:
            return _invalid(
                agent_id, "update_will", f"beneficiary {beneficiary_id} does not exist"
            )
    return action


def _validate_inspect(
    agent_id: str, action: InspectAction, world: WorldState, agent: Agent
) -> Action:
    target = world.agents.get(action.target_agent)
    if target is None or not target.alive:
        return _invalid(
            agent_id, "inspect", f"target agent {action.target_agent} not found or dead"
        )
    if target.location != agent.location:
        return _invalid(
            agent_id,
            "inspect",
            f"target agent {action.target_agent} at {target.location}, not at {agent.location}",
        )
    return action


# ============================================================================
# Resolution
# ============================================================================


def resolve_actions(
    world: WorldState, actions: dict[str, Action]
) -> list[ActionResult]:
    """Resolve all validated actions for a tick.

    Generates a random priority ordering using world.rng, then resolves
    actions in priority order for conflict-sensitive operations.
    Returns one ActionResult per agent.
    """
    if not actions:
        return []

    results: list[ActionResult] = []

    # Generate deterministic priority ordering
    agent_ids = list(actions.keys())
    priority_order = world.rng.sample(agent_ids, len(agent_ids))

    # Track which orders have been accepted this tick (for conflict resolution)
    accepted_orders: set[str] = set()

    for agent_id in priority_order:
        action = actions[agent_id]
        result = _resolve_single(agent_id, action, world, accepted_orders)
        results.append(result)

    # NPC auto-fill sell orders using iterative per-unit pricing
    _resolve_npc_sells(world)

    return results


def _resolve_single(
    agent_id: str,
    action: Action,
    world: WorldState,
    accepted_orders: set[str],
) -> ActionResult:
    """Resolve a single agent's action."""
    match action.action_type:
        case "move":
            return _resolve_move(agent_id, action, world)  # type: ignore[arg-type]
        case "harvest":
            return _resolve_harvest(agent_id, action, world)  # type: ignore[arg-type]
        case "post_order":
            return _resolve_post_order(agent_id, action, world)  # type: ignore[arg-type]
        case "accept_order":
            return _resolve_accept_order(agent_id, action, world, accepted_orders)  # type: ignore[arg-type]
        case "propose_trade":
            return _resolve_propose_trade(agent_id, action, world)  # type: ignore[arg-type]
        case "accept_trade":
            return _resolve_accept_trade(agent_id, action, world)  # type: ignore[arg-type]
        case "send_message":
            return _resolve_send_message(agent_id, action, world)  # type: ignore[arg-type]
        case "update_will":
            return _resolve_update_will(agent_id, action, world)  # type: ignore[arg-type]
        case "inspect":
            return _resolve_inspect(agent_id, action, world)  # type: ignore[arg-type]
        case "idle":
            return ActionResult(
                agent_id=agent_id, action=action, success=True, detail="Idle"
            )

    return ActionResult(
        agent_id=agent_id,
        action=action,
        success=False,
        detail=f"Unknown action type: {action.action_type}",
    )


def _resolve_move(agent_id: str, action: MoveAction, world: WorldState) -> ActionResult:
    agent = world.agents[agent_id]
    old_location = agent.location

    # Suspend orders at departure node
    suspend_orders_for_agent(world, agent_id, old_location)

    agent.location = action.target_node

    # Reactivate orders at arrival node
    reactivate_orders_for_agent(world, agent_id, action.target_node)

    return ActionResult(
        agent_id=agent_id,
        action=action,
        success=True,
        detail=f"Moved to {action.target_node}",
    )


def _resolve_harvest(
    agent_id: str, action: HarvestAction, world: WorldState
) -> ActionResult:
    agent = world.agents[agent_id]
    node = world.nodes[agent.location]

    # Find commodity with highest floor(stockpile)
    best_commodity: CommodityType | None = None
    best_floor = 0
    for commodity, stockpile in node.resource_stockpile.items():
        floored = math.floor(stockpile)
        if floored > best_floor:
            best_floor = floored
            best_commodity = commodity

    if best_commodity is None or best_floor < 1:
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=False,
            detail=f"No harvestable resources at {agent.location}",
        )

    # Harvest 1 unit
    node.resource_stockpile[best_commodity] -= 1.0
    agent.inventory[best_commodity] = agent.inventory.get(best_commodity, 0) + 1

    return ActionResult(
        agent_id=agent_id,
        action=action,
        success=True,
        detail=f"Harvested 1 {best_commodity.value} at {agent.location}",
    )


def _resolve_post_order(
    agent_id: str, action: PostOrderAction, world: WorldState
) -> ActionResult:
    side = BuySell.BUY if action.side == "buy" else BuySell.SELL
    result = post_order(
        world,
        agent_id,
        side=side,
        commodity=action.commodity,
        quantity=action.quantity,
        price_per_unit=action.price,
    )
    if result is None:
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=False,
            detail="Failed to post order (limit reached or insufficient resources)",
        )

    return ActionResult(
        agent_id=agent_id,
        action=action,
        success=True,
        detail=(
            f"Posted {action.side} order {result.order_id}: "
            f"{action.quantity} {action.commodity.value} @ {action.price}"
        ),
    )


def _resolve_accept_order(
    agent_id: str,
    action: AcceptOrderAction,
    world: WorldState,
    accepted_orders: set[str],
) -> ActionResult:
    # Conflict check: already accepted this tick?
    if action.order_id in accepted_orders:
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=False,
            detail=f"Order {action.order_id} already accepted by higher-priority agent",
        )

    trade_result = accept_order(world, agent_id, action.order_id)

    if trade_result.success:
        accepted_orders.add(action.order_id)
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=True,
            detail=f"Accepted order {action.order_id}: {trade_result.credits_transferred} credits",
        )
    else:
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=False,
            detail=f"Order {action.order_id} failed: {trade_result.failure_reason}",
        )


def _resolve_propose_trade(
    agent_id: str, action: ProposeTradeAction, world: WorldState
) -> ActionResult:
    # Convert action offer/request to trading module format
    offer_commodities: dict[CommodityType, int] = {}
    offer_credits: Millicredits = 0
    for key, qty in action.offer.items():
        if key == "credits":
            offer_credits = qty
        else:
            offer_commodities[CommodityType(key)] = qty

    request_commodities: dict[CommodityType, int] = {}
    request_credits: Millicredits = 0
    for key, qty in action.request.items():
        if key == "credits":
            request_credits = qty
        else:
            request_commodities[CommodityType(key)] = qty

    result = propose_trade(
        world,
        agent_id,
        action.target_agent,
        offer_commodities=offer_commodities if offer_commodities else None,
        offer_credits=offer_credits,
        request_commodities=request_commodities if request_commodities else None,
        request_credits=request_credits,
    )

    if result is None:
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=False,
            detail="Failed to propose trade",
        )

    return ActionResult(
        agent_id=agent_id,
        action=action,
        success=True,
        detail=f"Proposed trade {result.trade_id} to {action.target_agent}",
    )


def _resolve_accept_trade(
    agent_id: str, action: AcceptTradeAction, world: WorldState
) -> ActionResult:
    trade_result = accept_trade(world, agent_id, action.trade_id)

    if trade_result.success:
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=True,
            detail=f"Accepted trade {action.trade_id}",
        )
    else:
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=False,
            detail=f"Trade {action.trade_id} failed: {trade_result.failure_reason}",
        )


def _resolve_send_message(
    agent_id: str, action: SendMessageAction, world: WorldState
) -> ActionResult:
    agent = world.agents[agent_id]

    # Map "all" target to "broadcast" for communication module
    recipient = "broadcast" if action.target == "all" else action.target

    # Delegate to communication module
    comm_action = CommSendMessageAction(
        sender_id=agent_id,
        recipient=recipient,
        text=action.text,
    )
    result = send_message(world, comm_action)

    if result is None:
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=False,
            detail=f"Failed to send message to {action.target}",
        )

    if action.target == "all":
        detail = f"Broadcast message at {agent.location}"
    else:
        detail = f"Sent message to {action.target}"

    return ActionResult(agent_id=agent_id, action=action, success=True, detail=detail)


def _resolve_update_will(
    agent_id: str, action: UpdateWillAction, world: WorldState
) -> ActionResult:
    # Delegate to inheritance module for full validation
    result = update_will(world, agent_id, dict(action.distribution))

    if result.success:
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=True,
            detail=f"Updated will: {len(action.distribution)} beneficiaries",
        )
    else:
        return ActionResult(
            agent_id=agent_id,
            action=action,
            success=False,
            detail=f"Will update failed: {result.error}",
        )


def _resolve_inspect(
    agent_id: str, action: InspectAction, world: WorldState
) -> ActionResult:
    target = world.agents[action.target_agent]
    inventory_summary = ", ".join(
        f"{qty} {ct.value}" for ct, qty in target.inventory.items() if qty > 0
    )
    if not inventory_summary:
        inventory_summary = "empty"

    detail = (
        f"Inspected {action.target_agent}: "
        f"credits={target.credits}, inventory=[{inventory_summary}], age={target.age}"
    )
    return ActionResult(agent_id=agent_id, action=action, success=True, detail=detail)


def _resolve_npc_sells(world: WorldState) -> None:
    """Auto-fill open sell orders where NPCs can buy the commodity.

    Uses the economy module's iterative per-unit pricing via process_npc_sell.
    Processes orders in order_id sequence.
    """
    from evomarket.engine.trading import OrderStatus

    orders_to_fill: list[str] = []

    for order_id in sorted(world.order_book.keys()):
        order = world.order_book[order_id]
        if getattr(order, "side", None) != BuySell.SELL:
            continue
        if getattr(order, "status", None) != OrderStatus.ACTIVE:
            continue

        node_id = getattr(order, "node_id", None)
        commodity = getattr(order, "commodity", None)
        node = world.nodes[node_id]

        if commodity not in node.npc_buys:
            continue

        # Check NPC can afford at least something at current price
        unit_price = world.get_npc_price(node_id, commodity)
        if unit_price == 0 or node.npc_budget < unit_price:
            continue

        orders_to_fill.append(order_id)

    for order_id in orders_to_fill:
        order = world.order_book.get(order_id)
        if order is None:
            continue

        agent_id = getattr(order, "poster_id", None)
        commodity = getattr(order, "commodity", None)
        quantity = getattr(order, "quantity", 0)
        node_id = getattr(order, "node_id", None)

        # Restore escrowed inventory to agent so process_npc_sell can work
        agent = world.agents[agent_id]
        agent.inventory[commodity] = agent.inventory.get(commodity, 0) + quantity

        # Use economy module's iterative pricing
        result = process_npc_sell(world, agent_id, commodity, quantity)

        # If some units couldn't be sold, remove them from inventory again
        unsold = quantity - result.units_sold
        if unsold > 0:
            agent.inventory[commodity] -= unsold

        # Cancel the order (it's been processed)
        from evomarket.engine.trading import OrderStatus as OS

        order.status = OS.FILLED
