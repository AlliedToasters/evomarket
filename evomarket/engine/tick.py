"""Tick engine — 10-phase tick resolution pipeline."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from evomarket.core.types import Millicredits, NodeType
from evomarket.engine.actions import (
    Action,
    ActionResult,
    AgentTurnResult,
    resolve_actions,
    validate_action,
)
from evomarket.engine.communication import (
    clear_messages_for_agent,
    deliver_pending_messages,
)
from evomarket.engine.economy import (
    ReplenishResult,
    TaxResult,
    collect_tax,
    decay_npc_stockpiles,
    replenish_npc_budgets,
)
from evomarket.engine.inheritance import DeathResult, resolve_deaths
from evomarket.engine.observation import AgentObservation, generate_observations
from evomarket.engine.spawning import SpawnResult, spawn_agents
from evomarket.engine.trading import (
    cancel_all_orders_for_agent,
    expire_pending_trades,
)

if TYPE_CHECKING:
    from evomarket.core.world import WorldState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums and models
# ---------------------------------------------------------------------------


class TickPhase(str, Enum):
    """The 10 phases of a tick, in execution order."""

    RECEIVE = "RECEIVE"
    OBSERVE = "OBSERVE"
    DECIDE = "DECIDE"
    VALIDATE = "VALIDATE"
    RESOLVE = "RESOLVE"
    TAX = "TAX"
    DEATH = "DEATH"
    SPAWN = "SPAWN"
    REPLENISH = "REPLENISH"
    LOG = "LOG"


@dataclass(frozen=True)
class TickMetrics:
    """Aggregate statistics for a single tick."""

    total_credits_in_circulation: Millicredits
    agent_credit_gini: float
    total_trade_volume: Millicredits
    trades_executed: int
    agents_alive: int
    agents_died: int
    agents_spawned: int
    total_resources_harvested: int
    total_npc_sales: int
    total_messages_sent: int


@dataclass(frozen=True)
class TickResult:
    """Complete outcome of a single tick."""

    tick: int
    action_results: list[ActionResult]
    tax_results: list[TaxResult]
    death_results: list[DeathResult]
    spawn_results: list[SpawnResult]
    replenish_result: ReplenishResult
    metrics: TickMetrics
    invariant_check: bool


# ---------------------------------------------------------------------------
# Resource regeneration
# ---------------------------------------------------------------------------


def regenerate_resources(world: WorldState) -> None:
    """Add resources to RESOURCE nodes, capped at resource_cap."""
    for node in world.nodes.values():
        if node.node_type != NodeType.RESOURCE:
            continue
        for commodity, weight in node.resource_distribution.items():
            increment = node.resource_spawn_rate * weight
            current = node.resource_stockpile.get(commodity, 0.0)
            node.resource_stockpile[commodity] = min(
                current + increment, float(node.resource_cap)
            )


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------


def _compute_gini(values: list[Millicredits]) -> float:
    """Compute the Gini coefficient for a list of non-negative values."""
    if not values:
        return 0.0
    n = len(values)
    if n == 1:
        return 0.0
    total = sum(values)
    if total == 0:
        return 0.0
    sorted_vals = sorted(values)
    cumulative = 0.0
    weighted_sum = 0.0
    for i, v in enumerate(sorted_vals):
        cumulative += v
        weighted_sum += (2 * (i + 1) - n - 1) * v
    return weighted_sum / (n * total)


def _compute_metrics(
    world: WorldState,
    action_results: list[ActionResult],
    death_results: list[DeathResult],
    spawn_results: list[SpawnResult],
) -> TickMetrics:
    """Compute aggregate metrics for the tick."""
    agent_credits = [a.credits for a in world.agents.values() if a.alive]

    # Count harvests from action results
    harvests = sum(
        1 for r in action_results if r.success and r.action.action_type == "harvest"
    )

    # Count trades (accept_order and accept_trade)
    trades = sum(
        1
        for r in action_results
        if r.success and r.action.action_type in ("accept_order", "accept_trade")
    )

    # Sum trade volume from structured credits_transferred field
    trade_volume: Millicredits = sum(
        r.credits_transferred
        for r in action_results
        if r.success
        and r.action.action_type in ("accept_order", "accept_trade")
    )

    # Count NPC sales (flagged by resolve_actions)
    npc_sales = sum(1 for r in action_results if r.success and r.npc_sale)

    # Count messages sent
    messages = sum(
        1
        for r in action_results
        if r.success and r.action.action_type == "send_message"
    )

    return TickMetrics(
        total_credits_in_circulation=sum(agent_credits),
        agent_credit_gini=_compute_gini(agent_credits),
        total_trade_volume=trade_volume,
        trades_executed=trades,
        agents_alive=len(agent_credits),
        agents_died=len(death_results),
        agents_spawned=len(spawn_results),
        total_resources_harvested=harvests,
        total_npc_sales=npc_sales,
        total_messages_sent=messages,
    )


# ---------------------------------------------------------------------------
# Main tick execution
# ---------------------------------------------------------------------------

# Type alias for the agent decisions callable
AgentDecisionsFn = Callable[[dict[str, AgentObservation]], dict[str, AgentTurnResult]]


def execute_tick(
    world: WorldState,
    agent_decisions: AgentDecisionsFn,
    debug: bool = False,
) -> TickResult:
    """Execute a single tick through the 10-phase pipeline.

    Args:
        world: Mutable world state (mutated in place).
        agent_decisions: Callable that maps observations to agent turn results.
        debug: If True, verify invariant after every phase.

    Returns:
        TickResult capturing all outcomes.
    """
    current_tick = world.tick

    def _check_invariant() -> None:
        if debug:
            world.verify_invariant()

    # Phase 1: RECEIVE — deliver pending messages
    deliver_pending_messages(world)
    _check_invariant()

    # Phase 2: OBSERVE — generate per-agent observations
    observations = generate_observations(world)
    _check_invariant()

    # Phase 3: DECIDE — get agent decisions
    turn_results = agent_decisions(observations)

    # Apply scratchpad updates
    for agent_id, turn in turn_results.items():
        if turn.scratchpad_update is not None:
            agent = world.agents.get(agent_id)
            if agent is not None and agent.alive:
                agent.prompt_document = turn.scratchpad_update

    _check_invariant()

    # Phase 4: VALIDATE — validate actions
    validated_actions: dict[str, Action] = {}
    for agent_id, turn in turn_results.items():
        agent = world.agents.get(agent_id)
        if agent is not None and agent.alive:
            validated_actions[agent_id] = validate_action(agent_id, turn.action, world)

    _check_invariant()

    # Phase 5: RESOLVE — expire old proposals, then resolve actions
    expire_pending_trades(world, max_age=1)
    action_results = resolve_actions(world, validated_actions)
    _check_invariant()

    # Phase 6: TAX — collect survival tax
    tax_results: list[TaxResult] = []
    dead_agent_ids: list[str] = []

    for agent_id, agent in world.agents.items():
        if not agent.alive:
            continue
        if agent.grace_ticks_remaining > 0:
            agent.grace_ticks_remaining -= 1
            continue
        result = collect_tax(world, agent_id, world.config.survival_tax)
        tax_results.append(result)
        if result.remaining_balance <= 0:
            dead_agent_ids.append(agent_id)

    _check_invariant()

    # Phase 7: DEATH — resolve deaths with cleanup callbacks
    death_results = resolve_deaths(
        world,
        dead_agent_ids,
        cancel_orders_fn=cancel_all_orders_for_agent,
        clear_messages_fn=clear_messages_for_agent,
    )
    _check_invariant()

    # Phase 8: SPAWN — replace dead agents
    spawn_results = spawn_agents(world)
    _check_invariant()

    # Phase 9: REPLENISH — NPC budgets, resources, stockpile decay
    replenish_result = replenish_npc_budgets(world)
    regenerate_resources(world)
    decay_npc_stockpiles(world)
    _check_invariant()

    # Phase 10: LOG — age agents, compute metrics
    for agent in world.agents.values():
        if agent.alive:
            agent.age += 1

    metrics = _compute_metrics(world, action_results, death_results, spawn_results)

    # Increment tick counter
    world.tick += 1

    # End-of-tick invariant check (always)
    invariant_ok = True
    try:
        world.verify_invariant()
    except AssertionError:
        invariant_ok = False
        if not debug:
            raise

    if debug:
        _check_invariant()

    return TickResult(
        tick=current_tick,
        action_results=action_results,
        tax_results=tax_results,
        death_results=death_results,
        spawn_results=spawn_results,
        replenish_result=replenish_result,
        metrics=metrics,
        invariant_check=invariant_ok,
    )
