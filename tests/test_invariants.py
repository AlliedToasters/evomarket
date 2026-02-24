"""Property-based tests for the fixed-supply invariant."""

from hypothesis import given, settings, strategies as st

from evomarket.core.world import WorldConfig, WorldState, generate_world
from evomarket.engine.actions import AgentTurnResult, IdleAction
from evomarket.engine.observation import AgentObservation
from evomarket.engine.tick import execute_tick


def _make_world() -> WorldState:
    config = WorldConfig(num_nodes=5, num_commodity_types=2, population_size=3)
    return generate_world(config, seed=42)


def _reservoir_ids(world: WorldState) -> list[str]:
    """All valid reservoir IDs."""
    ids = list(world.agents.keys()) + list(world.nodes.keys()) + ["treasury"]
    return ids


def _idle_decisions(
    observations: dict[str, AgentObservation],
) -> dict[str, AgentTurnResult]:
    return {agent_id: AgentTurnResult(action=IdleAction()) for agent_id in observations}


@given(
    seed=st.integers(min_value=0, max_value=1000),
    num_transfers=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=50, deadline=None)
def test_invariant_after_random_transfers(seed: int, num_transfers: int) -> None:
    """The fixed-supply invariant holds after arbitrary sequences of valid transfers."""
    import random

    world = _make_world()
    rng = random.Random(seed)
    reservoirs = _reservoir_ids(world)

    for _ in range(num_transfers):
        src = rng.choice(reservoirs)
        dst = rng.choice(reservoirs)
        if src == dst:
            continue

        # Get source balance
        balance = world._get_balance(src)
        if balance <= 0:
            continue

        amount = rng.randint(1, max(1, balance))
        try:
            world.transfer_credits(src, dst, amount)
        except ValueError:
            # Insufficient funds — expected, skip
            pass

    world.verify_invariant()


@given(seed=st.integers(min_value=0, max_value=500))
@settings(max_examples=30, deadline=None)
def test_invariant_after_world_generation(seed: int) -> None:
    """The invariant holds for any generation seed."""
    config = WorldConfig(num_nodes=5, num_commodity_types=2, population_size=3)
    world = generate_world(config, seed=seed)
    world.verify_invariant()


@given(
    seed=st.integers(min_value=0, max_value=500),
    num_ticks=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=30, deadline=None)
def test_invariant_after_tick_cycles(seed: int, num_ticks: int) -> None:
    """The fixed-supply invariant holds after arbitrary sequences of full tick cycles."""
    config = WorldConfig(num_nodes=5, num_commodity_types=2, population_size=3)
    world = generate_world(config, seed=seed)

    for _ in range(num_ticks):
        result = execute_tick(world, _idle_decisions)
        assert result.invariant_check is True
        world.verify_invariant()


@given(seed=st.integers(min_value=0, max_value=200))
@settings(max_examples=20, deadline=None)
def test_invariant_with_deaths_and_spawns(seed: int) -> None:
    """Invariant holds through death/spawn cycles with depleted agents."""
    config = WorldConfig(
        num_nodes=5,
        num_commodity_types=2,
        population_size=3,
        starting_credits=5_000,  # Low credits to trigger deaths faster
        survival_tax=2_000,
        spawn_grace_period=1,
    )
    world = generate_world(config, seed=seed)

    for _ in range(15):
        result = execute_tick(world, _idle_decisions)
        assert result.invariant_check is True
        world.verify_invariant()
