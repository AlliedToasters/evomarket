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

ACTIONS (one per tick):
  move <node_id>                        — move to adjacent node
  harvest                               — gather resource (RESOURCE nodes only)
  post_order sell|buy <commodity> <qty> <price> — post order
  accept_order <order_id>               — fill an existing order
  propose_trade <agent_id> offer:<items> request:<items> — P2P trade
  accept_trade <trade_id>               — accept incoming trade
  send_message <target|broadcast> <text> — send message
  inspect <agent_id>                    — inspect nearby agent
  update_will <agent_id>=<pct> ...      — set inheritance
  idle                                  — do nothing

Commodities: IRON, WOOD, STONE, HERBS. Prices in credits.
NPC buys at nodes: price = base*(1-stockpile/capacity). High stock=low price.
Scratchpad tokens: {scratchpad_tokens}

RESPOND EXACTLY:
ACTION: <action_string>
SCRATCHPAD: <notes to remember next tick> (optional)
REASONING: <brief explanation> (optional)"""


def _render_preamble(agent_id: str, scratchpad: str) -> str:
    """Render the immutable preamble with live scratchpad token count."""
    return _PREAMBLE_TEMPLATE.format(
        agent_id=agent_id,
        tax_info="0.5cr",
        scratchpad_tokens=_approx_tokens(scratchpad),
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
    lines.append(f"You: credits={_mc(s.credits)} inv=[{inv_str}] age={s.age} at={s.location}")
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
            offer = ", ".join(
                f"{c.value}={q}" for c, q in p.offer_commodities.items()
            )
            if p.offer_credits > 0:
                offer += f", credits={_mc(p.offer_credits)}" if offer else f"credits={_mc(p.offer_credits)}"
            req = ", ".join(
                f"{c.value}={q}" for c, q in p.request_commodities.items()
            )
            if p.request_credits > 0:
                req += f", credits={_mc(p.request_credits)}" if req else f"credits={_mc(p.request_credits)}"
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
        _render_preamble(agent_id, scratchpad),
        _render_scratchpad(scratchpad),
        _render_world_state(observation),
    ]
    return "\n\n".join(parts)
