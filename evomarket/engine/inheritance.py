"""Will management, death resolution, and estate distribution."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from evomarket.core.types import CommodityType, Millicredits
from evomarket.core.world import WorldState


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class WillUpdateResult(BaseModel):
    """Result of a will update attempt."""

    model_config = ConfigDict(frozen=True)

    success: bool
    error: str | None = None


class WillTransfer(BaseModel):
    """Record of a single beneficiary's share from a will."""

    model_config = ConfigDict(frozen=True)

    beneficiary_id: str
    credits: Millicredits
    commodities: dict[CommodityType, int]
    will_percentage: float
    alive: bool


class DeathResult(BaseModel):
    """Full accounting of a single agent death resolution."""

    model_config = ConfigDict(frozen=True)

    agent_id: str
    total_estate_credits: Millicredits
    total_estate_commodities: dict[CommodityType, int]
    will_distributions: list[WillTransfer]
    unclaimed_credits: Millicredits
    unclaimed_commodities: dict[CommodityType, int]
    local_share_credits: Millicredits
    treasury_return: Millicredits
    commodities_destroyed: dict[CommodityType, int]


# Type alias for cleanup callbacks
CleanupFn = Callable[[WorldState, str], None]


def _noop_cleanup(world: WorldState, agent_id: str) -> None:  # noqa: ARG001
    """Default no-op cleanup callback."""


# ---------------------------------------------------------------------------
# Will management
# ---------------------------------------------------------------------------


def update_will(
    world: WorldState,
    agent_id: str,
    distribution: dict[str, float],
) -> WillUpdateResult:
    """Update an agent's will.

    Validates:
    - All beneficiary IDs exist in world.agents
    - All percentages are >= 0
    - Total percentages <= 1.0

    Replaces the agent's current will entirely on success.
    """
    for beneficiary_id in distribution:
        if beneficiary_id not in world.agents:
            return WillUpdateResult(
                success=False,
                error=f"Beneficiary '{beneficiary_id}' is not a valid agent ID",
            )

    for beneficiary_id, pct in distribution.items():
        if pct < 0:
            return WillUpdateResult(
                success=False,
                error=f"Percentage for '{beneficiary_id}' is negative: {pct}",
            )

    total = sum(distribution.values())
    if total > 1.0 + 1e-9:
        return WillUpdateResult(
            success=False,
            error=f"Will percentages sum to {total}, must be <= 1.0",
        )

    world.agents[agent_id].will = distribution
    return WillUpdateResult(success=True)


def get_will(world: WorldState, agent_id: str) -> dict[str, float]:
    """Return an agent's current will distribution."""
    return dict(world.agents[agent_id].will)


# ---------------------------------------------------------------------------
# Death resolution
# ---------------------------------------------------------------------------


def _calculate_estate(
    world: WorldState,
    agent_id: str,
) -> tuple[Millicredits, dict[CommodityType, int]]:
    """Calculate the total estate of a dying agent."""
    agent = world.agents[agent_id]
    credits = max(agent.credits, 0)  # clamp negative balances to 0
    commodities = {c: qty for c, qty in agent.inventory.items() if qty > 0}
    return credits, commodities


def _execute_will(
    world: WorldState,
    agent_id: str,
    estate_credits: Millicredits,
    estate_commodities: dict[CommodityType, int],
) -> tuple[list[WillTransfer], Millicredits, dict[CommodityType, int]]:
    """Execute will transfers, returning transfers, unclaimed credits, unclaimed commodities."""
    agent = world.agents[agent_id]
    will = agent.will

    transfers: list[WillTransfer] = []
    claimed_credits: Millicredits = 0
    claimed_commodities: dict[CommodityType, int] = {c: 0 for c in estate_commodities}

    for beneficiary_id, pct in will.items():
        beneficiary = world.agents.get(beneficiary_id)
        is_alive = beneficiary is not None and beneficiary.alive

        # Calculate this beneficiary's share (floor division)
        credit_share = int(estate_credits * pct)
        commodity_share = {c: int(qty * pct) for c, qty in estate_commodities.items()}

        if is_alive:
            # Transfer credits
            if credit_share > 0:
                world.transfer_credits(agent_id, beneficiary_id, credit_share)
            claimed_credits += credit_share

            # Transfer commodities
            for c, qty in commodity_share.items():
                if qty > 0:
                    agent.inventory[c] -= qty
                    beneficiary.inventory[c] += qty
                    claimed_commodities[c] = claimed_commodities.get(c, 0) + qty

        transfers.append(
            WillTransfer(
                beneficiary_id=beneficiary_id,
                credits=credit_share,
                commodities=commodity_share,
                will_percentage=pct,
                alive=is_alive,
            )
        )

    unclaimed_credits = estate_credits - claimed_credits
    unclaimed_commodities = {
        c: estate_commodities.get(c, 0) - claimed_commodities.get(c, 0)
        for c in estate_commodities
        if estate_commodities.get(c, 0) - claimed_commodities.get(c, 0) > 0
    }

    return transfers, unclaimed_credits, unclaimed_commodities


def _distribute_unclaimed(
    world: WorldState,
    agent_id: str,
    unclaimed_credits: Millicredits,
    unclaimed_commodities: dict[CommodityType, int],
) -> tuple[Millicredits, Millicredits, dict[CommodityType, int]]:
    """Distribute unclaimed estate portion. Returns (local_share, treasury_return, destroyed)."""
    config = world.config
    agent = world.agents[agent_id]

    # Find living agents at the deceased's node (excluding the deceased)
    local_agents = [
        a for a in world.agents_at_node(agent.location) if a.agent_id != agent_id
    ]

    # Split credits
    local_share_total = int(unclaimed_credits * config.death_local_share_pct)
    treasury_share = unclaimed_credits - local_share_total  # remainder goes to treasury

    local_share_distributed: Millicredits = 0

    if local_agents and local_share_total > 0:
        per_agent = local_share_total // len(local_agents)
        if per_agent > 0:
            for la in local_agents:
                world.transfer_credits(agent_id, la.agent_id, per_agent)
                local_share_distributed += per_agent
        # Rounding remainder goes to treasury
        local_remainder = local_share_total - local_share_distributed
        treasury_share += local_remainder
    else:
        # No local agents — local share goes to treasury
        treasury_share += local_share_total
        local_share_total = 0

    # Transfer remaining credits to treasury
    remaining_on_agent = agent.credits
    if remaining_on_agent > 0:
        world.transfer_credits(agent_id, "treasury", remaining_on_agent)

    # Destroy unclaimed commodities (remove from agent inventory)
    for c, qty in unclaimed_commodities.items():
        if qty > 0 and agent.inventory.get(c, 0) >= qty:
            agent.inventory[c] -= qty

    return local_share_distributed, treasury_share, unclaimed_commodities


def resolve_death(
    world: WorldState,
    agent_id: str,
    cancel_orders_fn: CleanupFn | None = None,
    clear_messages_fn: CleanupFn | None = None,
) -> DeathResult:
    """Resolve a single agent death: estate calculation, will execution, unclaimed distribution, cleanup."""
    if cancel_orders_fn is None:
        cancel_orders_fn = _noop_cleanup
    if clear_messages_fn is None:
        clear_messages_fn = _noop_cleanup

    # Step 1: Calculate estate
    estate_credits, estate_commodities = _calculate_estate(world, agent_id)

    # Step 2: Execute will
    transfers, unclaimed_credits, unclaimed_commodities = _execute_will(
        world, agent_id, estate_credits, estate_commodities
    )

    # Step 3: Distribute unclaimed
    local_share, treasury_return, commodities_destroyed = _distribute_unclaimed(
        world, agent_id, unclaimed_credits, unclaimed_commodities
    )

    # Step 4: Cleanup
    world.agents[agent_id].alive = False
    cancel_orders_fn(world, agent_id)
    clear_messages_fn(world, agent_id)

    return DeathResult(
        agent_id=agent_id,
        total_estate_credits=estate_credits,
        total_estate_commodities=estate_commodities,
        will_distributions=transfers,
        unclaimed_credits=unclaimed_credits,
        unclaimed_commodities=unclaimed_commodities,
        local_share_credits=local_share,
        treasury_return=treasury_return,
        commodities_destroyed=commodities_destroyed,
    )


# ---------------------------------------------------------------------------
# Batch death resolution
# ---------------------------------------------------------------------------


def resolve_deaths(
    world: WorldState,
    dead_agent_ids: list[str],
    cancel_orders_fn: CleanupFn | None = None,
    clear_messages_fn: CleanupFn | None = None,
) -> list[DeathResult]:
    """Resolve multiple agent deaths in deterministic order (sorted by agent_id)."""
    results: list[DeathResult] = []
    for agent_id in sorted(dead_agent_ids):
        result = resolve_death(world, agent_id, cancel_orders_fn, clear_messages_fn)
        results.append(result)
    return results
