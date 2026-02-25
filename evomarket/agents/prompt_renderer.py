"""Prompt renderer — converts AgentObservation to a compact text prompt."""

from __future__ import annotations

from evomarket.core.types import MILLICREDITS_PER_CREDIT, Millicredits
from evomarket.engine.observation import AgentObservation


def _approx_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _mc(value: Millicredits) -> str:
    """Format millicredits as display credits."""
    return f"{value / MILLICREDITS_PER_CREDIT:.1f}"


# ---------------------------------------------------------------------------
# Preamble (immutable, compressed)
# ---------------------------------------------------------------------------

_PREAMBLE_TEMPLATE = """\
=== EVOMARKET AGENT ===
You are {agent_id}. Survive by earning credits. Tax={tax_info}/tick. Credits=0 → death.

HOW TO EARN CREDITS: move to a RESOURCE node → harvest → move to a TRADE_HUB → sell to NPC.
RESOURCE nodes have harvestable commodities. TRADE_HUB nodes have NPC buyers.
{strategic_hint}

VALID ACTIONS THIS TICK (pick one):
{valid_actions}

RESPOND WITH EXACTLY ONE LINE starting with ACTION:
ACTION: <action_string>
SCRATCHPAD: <notes for next tick> (optional)"""


def _get_valid_actions(obs: AgentObservation) -> list[str]:
    """Build list of valid actions from pre-computed ActionAvailability."""
    avail = obs.action_availability
    if avail is None:
        return ["  idle  — do nothing"]

    actions: list[str] = []

    # Move — show node types to help navigation
    if avail.can_move:
        if obs.node_info.adjacent_node_info:
            nodes = ", ".join(
                f"{a.node_id}({a.node_type})" for a in obs.node_info.adjacent_node_info
            )
        else:
            nodes = ", ".join(avail.adjacent_nodes)
        actions.append(f"  move <node_id>  — move to adjacent node ({nodes})")

    # Harvest
    if avail.can_harvest:
        res = ", ".join(
            f"{c.value}={q}" for c, q in avail.harvestable_resources.items()
        )
        actions.append(f"  harvest  — gather resource (available: {res})")

    # Sell to NPC
    if avail.can_sell_to_npc:
        for item in avail.sellable_items:
            price = item.npc_price / MILLICREDITS_PER_CREDIT
            actions.append(
                f"  sell {item.commodity.value} <qty> <price>  — sell to NPC (you have {item.quantity_held}, NPC pays ~{price:.1f}cr)"
            )

    # Buy from NPC
    if avail.can_buy_from_npc:
        actions.append("  buy <commodity> <qty> <price>  — buy from NPC")

    # Post sell order (only if agent has inventory)
    if avail.can_post_sell_order:
        inv_str = ", ".join(
            f"{c.value}={q}" for c, q in avail.post_sell_inventory.items()
        )
        actions.append(
            f"  post_order sell <commodity> <qty> <price>  — post sell order (you have: {inv_str})"
        )

    # Post buy order (only if agent has credits)
    if avail.can_post_buy_order:
        actions.append(
            f"  post_order buy <commodity> <qty> <price>  — post buy order (credits={_mc(obs.agent_state.credits)})"
        )

    # Accept order (fillable orders)
    for o in avail.fillable_orders:
        if o.side == "sell":
            actions.append(
                f"  accept_order {o.order_id}  — buy {o.commodity.value} x{o.quantity} @{_mc(o.price_per_unit)}cr from {o.poster_id}"
            )
        elif o.side == "buy":
            actions.append(
                f"  accept_order {o.order_id}  — sell {o.commodity.value} x{o.quantity} @{_mc(o.price_per_unit)}cr to {o.poster_id}"
            )

    # Propose trade
    if avail.can_propose_trade:
        agents = ", ".join(avail.tradeable_agents)
        actions.append(
            f"  propose_trade <agent_id> offer:<items> request:<items>  — trade with nearby agent ({agents})"
        )

    # Accept trade (only those the agent can fulfill)
    if avail.acceptable_trades:
        proposal_by_id = {p.trade_id: p for p in obs.pending_proposals}
        for trade_id in avail.acceptable_trades:
            p = proposal_by_id.get(trade_id)
            if p:
                actions.append(
                    f"  accept_trade {p.trade_id}  — accept trade from {p.proposer_id}"
                )

    # Communication — always available
    actions.append("  send_message <target|broadcast> <text>  — send message")

    # Inspect
    if avail.can_inspect:
        actions.append("  inspect <agent_id>  — inspect nearby agent")

    # Will — always available
    actions.append("  update_will <agent_id>=<pct> ...  — set inheritance")

    # Idle — always available
    actions.append("  idle  — do nothing")

    return actions


def _get_strategic_hint(obs: AgentObservation) -> str:
    """Generate a context-sensitive strategic hint based on current situation."""
    avail = obs.action_availability
    node_type = obs.node_info.node_type
    nearby_count = len(obs.agents_present)

    # Crowding warning — makes competition salient
    crowd_warning = ""
    if nearby_count >= 3:
        crowd_warning = (
            f" WARNING: {nearby_count} other agents here — resources are shared and"
            " will run out. Spread out to different RESOURCE nodes to avoid competition."
        )

    if node_type == "SPAWN":
        return "HINT: You are at SPAWN. Move out to find resources." + crowd_warning
    if avail and avail.can_harvest:
        return (
            "HINT: Resources available here! Use 'harvest' to gather them."
            + crowd_warning
        )
    if avail and avail.can_sell_to_npc:
        return "HINT: You have goods and there's an NPC buyer here. Sell for credits!"

    inv_count = sum(obs.agent_state.inventory.values())
    if inv_count > 0 and node_type == "RESOURCE":
        return "HINT: You have inventory. Move to a TRADE_HUB to sell to NPC."
    if inv_count > 0:
        return "HINT: You have inventory. Find a TRADE_HUB with NPC buyers to sell."
    if node_type == "TRADE_HUB":
        adj_hubs = [
            a for a in obs.node_info.adjacent_node_info if a.node_type == "TRADE_HUB"
        ]
        hint = "HINT: No inventory to sell. Move to a RESOURCE node to harvest."
        if adj_hubs:
            hub_names = ", ".join(a.node_id for a in adj_hubs)
            hint += (
                f" Other regions with different resources are reachable"
                f" through: {hub_names}."
            )
        return hint + crowd_warning
    return crowd_warning.lstrip()


def _render_preamble(agent_id: str, scratchpad: str, obs: AgentObservation) -> str:
    """Render the preamble with contextually valid actions."""
    valid_actions = "\n".join(_get_valid_actions(obs))
    strategic_hint = _get_strategic_hint(obs)
    return _PREAMBLE_TEMPLATE.format(
        agent_id=agent_id,
        tax_info="0.5cr",
        valid_actions=valid_actions,
        strategic_hint=strategic_hint,
    )


# ---------------------------------------------------------------------------
# Scratchpad
# ---------------------------------------------------------------------------


def _render_scratchpad(scratchpad: str) -> str:
    """Render the scratchpad section."""
    if not scratchpad:
        return "=== SCRATCHPAD ===\n(empty)"
    return f"=== SCRATCHPAD ===\n{scratchpad}"


# ---------------------------------------------------------------------------
# World state
# ---------------------------------------------------------------------------


def _render_world_state(obs: AgentObservation) -> str:
    """Render the world state section from an observation."""
    lines: list[str] = ["=== WORLD STATE ==="]

    # Tick
    lines.append(f"Tick: {obs.preamble.tick}")

    # Agent state
    s = obs.agent_state
    inv_parts = [f"{c.value}={q}" for c, q in s.inventory.items() if q > 0]
    inv_str = ", ".join(inv_parts) if inv_parts else "empty"
    lines.append(
        f"You: credits={_mc(s.credits)} inv=[{inv_str}] age={s.age} at={s.location}"
    )
    if s.grace_ticks_remaining > 0:
        lines.append(f"  Grace: {s.grace_ticks_remaining} ticks (no tax)")

    # Node info
    n = obs.node_info
    lines.append(f"Node: {n.node_id} ({n.name}) type={n.node_type}")
    if n.adjacent_node_info:
        adj_parts = [f"{a.node_id}({a.node_type})" for a in n.adjacent_node_info]
        lines.append(f"  Adjacent: {', '.join(adj_parts)}")
    else:
        lines.append(f"  Adjacent: {', '.join(n.adjacent_nodes)}")

    if n.npc_prices:
        prices = ", ".join(f"{c.value}={_mc(p)}" for c, p in n.npc_prices.items())
        lines.append(f"  NPC prices: {prices}")

    if n.resource_availability:
        avail = [f"{c.value}={q}" for c, q in n.resource_availability.items() if q > 0]
        if avail:
            lines.append(f"  Resources: {', '.join(avail)}")

    # Nearby agents — show count prominently for crowding awareness
    if obs.agents_present:
        count = len(obs.agents_present)
        agents = ", ".join(a.agent_id for a in obs.agents_present)
        lines.append(f"Nearby agents ({count}): {agents}")

    # Posted orders at node
    if obs.posted_orders:
        lines.append("Orders:")
        for o in obs.posted_orders:
            lines.append(
                f"  {o.order_id} {o.side} {o.commodity.value} x{o.quantity} @{_mc(o.price_per_unit)} by {o.poster_id}"
            )

    # Own orders (all nodes)
    if obs.own_orders:
        lines.append("Your orders:")
        for o in obs.own_orders:
            lines.append(
                f"  {o.order_id} {o.side} {o.commodity.value} x{o.quantity} @{_mc(o.price_per_unit)}"
            )

    # Incoming trade proposals
    if obs.pending_proposals:
        lines.append("Trade proposals:")
        for p in obs.pending_proposals:
            offer = ", ".join(f"{c.value}={q}" for c, q in p.offer_commodities.items())
            if p.offer_credits > 0:
                offer += (
                    f", credits={_mc(p.offer_credits)}"
                    if offer
                    else f"credits={_mc(p.offer_credits)}"
                )
            req = ", ".join(f"{c.value}={q}" for c, q in p.request_commodities.items())
            if p.request_credits > 0:
                req += (
                    f", credits={_mc(p.request_credits)}"
                    if req
                    else f"credits={_mc(p.request_credits)}"
                )
            lines.append(
                f"  {p.trade_id} from {p.proposer_id}: offers=[{offer}] wants=[{req}]"
            )

    # Messages
    if obs.messages_received:
        lines.append("Messages:")
        for m in obs.messages_received:
            lines.append(f"  [{m.sender_id} t{m.sent_tick}] {m.text}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_prompt(
    observation: AgentObservation,
    scratchpad: str,
    agent_id: str,
) -> str:
    """Render a complete prompt from an observation.

    Returns a string with three sections: preamble, scratchpad, world state.
    """
    parts = [
        _render_preamble(agent_id, scratchpad, observation),
        _render_scratchpad(scratchpad),
        _render_world_state(observation),
    ]
    return "\n\n".join(parts)
