"""Shared test fixtures for EvoMarket."""

import pytest

from evomarket.core.world import WorldConfig, WorldState, generate_world


@pytest.fixture
def small_world() -> WorldState:
    """Small world: 5 target nodes, 2 commodity types, 5 agents."""
    config = WorldConfig(
        num_nodes=5,
        num_commodity_types=2,
        population_size=5,
        total_credit_supply=10_000_000,
        starting_credits=30_000,
    )
    return generate_world(config, seed=42)


@pytest.fixture
def standard_world() -> WorldState:
    """Standard world: 15 nodes, 4 commodity types, 20 agents."""
    config = WorldConfig()  # all defaults
    return generate_world(config, seed=42)
