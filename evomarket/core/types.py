"""Shared types, enums, and constants for the EvoMarket core."""

from enum import Enum

# Type alias: all credit values are stored as int millicredits (1000 mc = 1 display credit)
Millicredits = int

MILLICREDITS_PER_CREDIT = 1000


class CommodityType(str, Enum):
    """Tradeable commodity types in the game world."""

    IRON = "IRON"
    WOOD = "WOOD"
    STONE = "STONE"
    HERBS = "HERBS"


class NodeType(str, Enum):
    """Types of nodes in the world graph."""

    RESOURCE = "RESOURCE"
    TRADE_HUB = "TRADE_HUB"
    SPAWN = "SPAWN"


def to_display_credits(mc: Millicredits) -> float:
    """Convert millicredits to display credits (float)."""
    return mc / MILLICREDITS_PER_CREDIT
