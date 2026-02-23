"""Resource distribution configuration and validation."""

from __future__ import annotations

from evomarket.core.types import CommodityType


def validate_resource_distribution(distribution: dict[CommodityType, float]) -> dict[CommodityType, float]:
    """Validate that resource distribution weights sum to at most 1.0.

    Each weight must be non-negative, and the total must not exceed 1.0.
    The remainder (1.0 - sum) represents the probability of no resource spawning.
    """
    for commodity, weight in distribution.items():
        if weight < 0:
            raise ValueError(f"Resource weight for {commodity} must be non-negative, got {weight}")
    total = sum(distribution.values())
    if total > 1.0 + 1e-9:  # small epsilon for float comparison on weights
        raise ValueError(f"Resource distribution weights sum to {total}, must be ≤ 1.0")
    return distribution
