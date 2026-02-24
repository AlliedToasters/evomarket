"""Action parser — extracts BaseAction from freeform LLM text responses."""

from __future__ import annotations

import logging
import re

from evomarket.core.types import CommodityType
from evomarket.engine.actions import (
    AcceptOrderAction,
    AcceptTradeAction,
    Action,
    HarvestAction,
    IdleAction,
    InspectAction,
    MoveAction,
    PostOrderAction,
    ProposeTradeAction,
    SendMessageAction,
    UpdateWillAction,
)

logger = logging.getLogger(__name__)

# Section prefixes in expected LLM response
_SECTION_PREFIXES = ("ACTION:", "SCRATCHPAD:", "REASONING:")

# Commodity name normalization
_COMMODITY_MAP: dict[str, CommodityType] = {}
for _ct in CommodityType:
    _COMMODITY_MAP[_ct.value.lower()] = _ct
    _COMMODITY_MAP[_ct.value.upper()] = _ct
    _COMMODITY_MAP[_ct.value.capitalize()] = _ct
    _COMMODITY_MAP[_ct.value] = _ct


def _normalize_commodity(text: str) -> CommodityType | None:
    """Try to match a commodity name, case-insensitive."""
    return _COMMODITY_MAP.get(text.strip())


def _parse_int(text: str) -> int | None:
    """Parse an integer, returning None on failure."""
    try:
        return int(text.strip())
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------


def _extract_sections(text: str) -> dict[str, str]:
    """Extract ACTION, SCRATCHPAD, and REASONING sections from response text."""
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        matched = False
        for prefix in _SECTION_PREFIXES:
            if stripped.upper().startswith(prefix):
                # Save previous section
                if current_key is not None:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = prefix.rstrip(":")
                current_lines = [stripped[len(prefix):].strip()]
                matched = True
                break
        if not matched and current_key is not None:
            current_lines.append(line)

    # Save last section
    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _extract_scratchpad(text: str) -> str | None:
    """Extract scratchpad content from response text."""
    sections = _extract_sections(text)
    content = sections.get("SCRATCHPAD", "").strip()
    return content if content else None


# ---------------------------------------------------------------------------
# Structured action parsing
# ---------------------------------------------------------------------------


def _parse_action_string(action_str: str) -> Action | None:
    """Parse a structured action string into an Action model."""
    parts = action_str.strip().split()
    if not parts:
        return None

    action_type = parts[0].lower().strip()
    args = parts[1:]

    try:
        return _dispatch_action(action_type, args)
    except (ValueError, IndexError, TypeError):
        return None


def _dispatch_action(action_type: str, args: list[str]) -> Action | None:
    """Dispatch to the appropriate action constructor."""
    if action_type == "idle":
        return IdleAction()

    elif action_type == "harvest":
        return HarvestAction()

    elif action_type == "move":
        if not args:
            return None
        return MoveAction(target_node=args[0])

    elif action_type in ("post_order", "postorder", "post"):
        return _parse_post_order(args)

    elif action_type in ("accept_order", "acceptorder"):
        if not args:
            return None
        return AcceptOrderAction(order_id=args[0])

    elif action_type in ("propose_trade", "proposetrade", "propose"):
        return _parse_propose_trade(args)

    elif action_type in ("accept_trade", "accepttrade"):
        if not args:
            return None
        return AcceptTradeAction(trade_id=args[0])

    elif action_type in ("send_message", "sendmessage", "send", "message"):
        return _parse_send_message(args)

    elif action_type == "inspect":
        if not args:
            return None
        return InspectAction(target_agent=args[0])

    elif action_type in ("update_will", "updatewill", "will"):
        return _parse_update_will(args)

    return None


def _parse_post_order(args: list[str]) -> Action | None:
    """Parse: sell|buy <commodity> <qty> <price>"""
    if len(args) < 4:
        return None
    side = args[0].lower()
    if side not in ("buy", "sell"):
        return None
    commodity = _normalize_commodity(args[1])
    if commodity is None:
        return None
    qty = _parse_int(args[2])
    price = _parse_int(args[3])
    if qty is None or qty <= 0 or price is None or price <= 0:
        return None
    return PostOrderAction(side=side, commodity=commodity, quantity=qty, price=price)


def _parse_propose_trade(args: list[str]) -> Action | None:
    """Parse: <agent_id> offer:<items> request:<items>

    Items format: key=value,key=value (e.g. offer:iron=2,credits=5000)
    """
    if len(args) < 3:
        return None
    target_agent = args[0]
    offer: dict[str, int] = {}
    request: dict[str, int] = {}

    for arg in args[1:]:
        if arg.lower().startswith("offer:"):
            offer = _parse_trade_items(arg[6:])
        elif arg.lower().startswith("request:"):
            request = _parse_trade_items(arg[8:])

    if not offer and not request:
        return None

    return ProposeTradeAction(target_agent=target_agent, offer=offer, request=request)


def _parse_trade_items(items_str: str) -> dict[str, int]:
    """Parse key=value pairs like 'iron=2,credits=5000'."""
    result: dict[str, int] = {}
    for pair in items_str.split(","):
        pair = pair.strip()
        if "=" not in pair:
            continue
        key, val_str = pair.split("=", 1)
        key = key.strip().lower()
        val = _parse_int(val_str)
        if val is None or val <= 0:
            continue
        # Normalize commodity names to uppercase enum values
        commodity = _normalize_commodity(key)
        if commodity is not None:
            result[commodity.value] = val
        elif key == "credits":
            result["credits"] = val
    return result


def _parse_send_message(args: list[str]) -> Action | None:
    """Parse: <target|broadcast> <text...>"""
    if not args:
        return None
    target = args[0]
    text = " ".join(args[1:]) if len(args) > 1 else ""
    return SendMessageAction(target=target, text=text)


def _parse_update_will(args: list[str]) -> Action | None:
    """Parse: <agent_id>=<pct> ..."""
    if not args:
        return None
    distribution: dict[str, float] = {}
    for arg in args:
        if "=" not in arg:
            continue
        agent_id, pct_str = arg.split("=", 1)
        try:
            pct = float(pct_str.strip())
        except ValueError:
            continue
        distribution[agent_id.strip()] = pct
    if not distribution:
        return None
    return UpdateWillAction(distribution=distribution)


# ---------------------------------------------------------------------------
# Regex fallback
# ---------------------------------------------------------------------------

# Patterns for keyword-based fallback extraction
_FALLBACK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bharvest\b", re.IGNORECASE), "harvest"),
    (re.compile(r"\bidle\b", re.IGNORECASE), "idle"),
    (re.compile(r"\bmove\s+(?:to\s+)?(node_\w+)", re.IGNORECASE), "move"),
    (re.compile(r"\binspect\s+(agent_\w+)", re.IGNORECASE), "inspect"),
    (re.compile(r"\baccept[_ ]?order\s+(\w+)", re.IGNORECASE), "accept_order"),
    (re.compile(r"\baccept[_ ]?trade\s+(\w+)", re.IGNORECASE), "accept_trade"),
]


def _regex_fallback(text: str) -> Action | None:
    """Try to extract action intent from freeform text using regex."""
    for pattern, action_type in _FALLBACK_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue

        if action_type == "harvest":
            return HarvestAction()
        elif action_type == "idle":
            return IdleAction()
        elif action_type == "move":
            return MoveAction(target_node=match.group(1))
        elif action_type == "inspect":
            return InspectAction(target_agent=match.group(1))
        elif action_type == "accept_order":
            return AcceptOrderAction(order_id=match.group(1))
        elif action_type == "accept_trade":
            return AcceptTradeAction(trade_id=match.group(1))

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_response(text: str) -> tuple[Action, str | None]:
    """Extract an Action and optional scratchpad update from LLM response text.

    Parsing strategy:
    1. Try structured parsing (ACTION: prefix)
    2. Regex fallback for keyword matching
    3. Default to IdleAction

    Every fallback to IdleAction is logged with the raw response.
    """
    if not text or not text.strip():
        logger.warning("parse_response: empty LLM response, defaulting to idle")
        return (IdleAction(), None)

    scratchpad = _extract_scratchpad(text)

    # Try structured parsing first
    sections = _extract_sections(text)
    action_str = sections.get("ACTION", "").strip()
    if action_str:
        action = _parse_action_string(action_str)
        if action is not None:
            return (action, scratchpad)

    # Regex fallback
    action = _regex_fallback(text)
    if action is not None:
        return (action, scratchpad)

    # Default to idle
    logger.warning(
        "parse_response: could not parse action from LLM response, "
        "defaulting to idle. Raw response: %s",
        text[:500],
    )
    return (IdleAction(), scratchpad)
