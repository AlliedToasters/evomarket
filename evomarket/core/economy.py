"""Economy primitives — re-exports from world module.

Treasury operations, NPC pricing, and credit transfers are methods on WorldState
(the centralized mutation point). This module provides a convenient import path
and documents the economy-related API surface.
"""

from evomarket.core.world import WorldState, generate_world

__all__ = ["WorldState", "generate_world"]
