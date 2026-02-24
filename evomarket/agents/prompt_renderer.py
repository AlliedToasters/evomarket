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

VALID ACTIONS THIS TICK (pick one):
{valid_actions}

Commodities: IRON, WOOD, STONE, HERBS. Prices in credits (e.g. 5.0).
NPC buys at nodes: price = base*(1-stockpile/capacity). High stock=low price.

RESPOND EXACTLY:
ACTION: <action_string>
SCRATCHPAD: <notes to remember next tick> (optional)
REASONING: <brief explanation> (optional)"""


def _get_valid_actions(obs: AgentObservation) -> list[str]:
    """Build list of valid actions based on current observation context."""
    actions: list[str] = []
    node = obs.node_info
    state = obs.agent_state
    inv = {c: q for c, q in state.inventory.items() if q > 0}

    # Move — always valid if there are adjacent nodes
    if node.adjacent_nodes:
        nodes = ", ".join(node.adjacent_nodes)
        actions.append(f"  move <node_id>  — move to adjacent node ({nodes})")

    # Harvest — only at RESOURCE nodes with available resources
    if node.node_type == "RESOURCE":
        avail = {c: q for c, q in node.resource_availability.items() if q > 0}
        if avail:
            res = ", ".join(f"{c.value}={q}" for c, q in avail.items())
            actions.append(f"  harvest  — gather resource (available: {res})")
        else:
            actions.append(
                "  harvest  — gather resource (none available now, will respawn)"
            )
    # No harvest line at all for non-RESOURCE nodes

    # Sell — only if agent has inventory and NPC buys here
    if inv and node.npc_prices:
        sellable = [(c, q) for c, q in inv.items() if c in node.npc_prices]
        if sellable:
            for c, q in sellable:
                price = node.npc_prices[c] / MILLICREDITS_PER_CREDIT
                actions.append(
                    f"  sell {c.value} <qty> <price>  — sell to NPC (you have {q}, NPC pays ~{price:.1f}cr)"
                )

    # Buy — if NPC has stock and agent has credits
    if node.npc_prices and state.credits > 0:
        actions.append("  buy <commodity> <qty> <price>  — buy from NPC")

    # Post order (generic) — always available
    actions.append(
        "  post_order sell|buy <commodity> <qty> <price>  — post limit order"
    )

    # Accept order — only if there are orders to accept
    if obs.posted_orders:
        for o in obs.posted_orders:
            actions.append(
                f"  accept_order {o.order_id}  — fill {o.side} {o.commodity.value} x{o.quantity} @{_mc(o.price_per_unit)}cr by {o.poster_id}"
            )

    # Propose trade — only if other agents are present
    if obs.agents_present:
        agents = ", ".join(a.agent_id for a in obs.agents_present)
        actions.append(
            f"  propose_trade <agent_id> offer:<items> request:<items>  — trade with nearby agent ({agents})"
        )

    # Accept trade — only if there are pending proposals
    if obs.pending_proposals:
        for p in obs.pending_proposals:
            actions.append(
                f"  accept_trade {p.trade_id}  — accept trade from {p.proposer_id}"
            )

    # Communication — always available
    actions.append("  send_message <target|broadcast> <text>  — send message")

    # Inspect — only if other agents are present
    if obs.agents_present:
        actions.append("  inspect <agent_id>  — inspect nearby agent")

    # Will — always available
    actions.append("  update_will <agent_id>=<pct> ...  — set inheritance")

    # Idle — always available
    actions.append("  idle  — do nothing")

    return actions


def _render_preamble(agent_id: str, scratchpad: str, obs: AgentObservation) -> str:
    """Render the preamble with contextually valid actions."""
    valid_actions = "\n".join(_get_valid_actions(obs))
    return _PREAMBLE_TEMPLATE.format(
        agent_id=agent_id,
        tax_info="0.5cr",
        valid_actions=valid_actions,
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
    lines.append(f"  Adjacent: {', '.join(n.adjacent_nodes)}")

    if n.npc_prices:
        prices = ", ".join(f"{c.value}={_mc(p)}" for c, p in n.npc_prices.items())
        lines.append(f"  NPC prices: {prices}")

    if n.resource_availability:
        avail = [f"{c.value}={q}" for c, q in n.resource_availability.items() if q > 0]
        if avail:
            lines.append(f"  Resources: {', '.join(avail)}")

    # Nearby agents
    if obs.agents_present:
        agents = ", ".join(a.agent_id for a in obs.agents_present)
        lines.append(f"Nearby: {agents}")

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
