"""Shared color palettes, widgets, and layout helpers for visualization panels."""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Color palettes
# ---------------------------------------------------------------------------

COMMODITY_COLORS: dict[str, str] = {
    "IRON": "#8B8B8B",
    "WOOD": "#8B5E3C",
    "STONE": "#6B7B8D",
    "HERBS": "#4CAF50",
}

AGENT_TYPE_COLORS: dict[str, str] = {
    "harvester": "#2E7D32",
    "trader": "#1565C0",
    "social": "#AB47BC",
    "hoarder": "#F57F17",
    "explorer": "#00838F",
    "random": "#757575",
    "llm": "#E53935",
}

# Palette for dynamically-named LLM backends (llm:haiku, llm:grok, etc.)
# Starts with colors distinct from the base "llm" red (#E53935).
_LLM_BACKEND_COLORS: list[str] = [
    "#8E24AA",  # purple
    "#FF6F00",  # amber
    "#00897B",  # teal
    "#3949AB",  # indigo
    "#E53935",  # red
    "#C62828",  # dark red
    "#6A1B9A",  # deep purple
    "#00695C",  # dark teal
]


def get_agent_color(agent_type: str, _seen: dict[str, str] = {}) -> str:
    """Return a color for an agent type, auto-assigning for llm:* types."""
    if agent_type in AGENT_TYPE_COLORS:
        return AGENT_TYPE_COLORS[agent_type]
    if agent_type in _seen:
        return _seen[agent_type]
    idx = len(_seen) % len(_LLM_BACKEND_COLORS)
    color = _LLM_BACKEND_COLORS[idx]
    _seen[agent_type] = color
    return color


NODE_TYPE_COLORS: dict[str, str] = {
    "RESOURCE": "#66BB6A",
    "TRADE_HUB": "#FFA726",
    "SPAWN": "#42A5F5",
}

# All commodity type strings for convenience
ALL_COMMODITIES: list[str] = ["IRON", "WOOD", "STONE", "HERBS"]


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------


def tick_range_selector(max_tick: int, key: str) -> tuple[int, int]:
    """Render a tick range slider. Returns (start_tick, end_tick)."""
    return st.slider(
        "Tick range",
        min_value=0,
        max_value=max_tick,
        value=(0, max_tick),
        key=key,
    )


def agent_filter(agent_ids: list[str], key: str) -> list[str]:
    """Render a multiselect for agent filtering. Empty selection means all."""
    selected = st.multiselect("Filter agents", options=agent_ids, key=key)
    return selected if selected else agent_ids


def commodity_selector(key: str) -> list[str]:
    """Render a multiselect for commodity filtering. Empty selection means all."""
    selected = st.multiselect("Commodities", options=ALL_COMMODITIES, key=key)
    return selected if selected else ALL_COMMODITIES


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_credits(mc_value: int) -> str:
    """Convert a millicredit integer to a formatted display credit string."""
    return f"{mc_value / 1000:.2f}"
