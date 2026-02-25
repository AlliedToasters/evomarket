"""Simulation runner — episode execution orchestrator."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp

from evomarket.agents.base import AgentFactory, BaseAgent
from evomarket.core.types import Millicredits, to_display_credits
from evomarket.core.world import WorldState, generate_world
from evomarket.engine.actions import AgentTurnResult, IdleAction
from evomarket.engine.observation import AgentObservation
from evomarket.engine.tick import TickMetrics, TickResult, execute_tick
from evomarket.simulation.config import SimulationConfig
from evomarket.simulation.logging import EventLogger

if TYPE_CHECKING:
    pass

# Type alias for stop condition callbacks
StopCondition = Callable[[int, WorldState, TickResult], bool]

logger = logging.getLogger(__name__)

# Order expiration age (ticks). Orders older than this are cancelled.
_ORDER_EXPIRY_TICKS = 10

# Action types considered "productive" for idle-streak detection
_PRODUCTIVE_ACTIONS = frozenset(
    {"harvest", "accept_order", "accept_trade", "propose_trade"}
)


def _tick_has_productive_action(tick_result: TickResult) -> bool:
    """Return True if any agent performed a productive action this tick."""
    for ar in tick_result.action_results:
        if not ar.success:
            continue
        if ar.action.action_type in _PRODUCTIVE_ACTIONS:
            return True
        if ar.npc_sale:
            return True
    return False


def idle_streak_stop(max_idle_ticks: int) -> StopCondition:
    """Create a stop condition that triggers after N consecutive unproductive ticks.

    A tick is "productive" if any agent successfully harvests, fills an order,
    completes a trade, or sells to an NPC. Posting buy/sell orders and idling
    are not productive.
    """
    streak = [0]  # mutable closure

    def _check(tick_num: int, world: WorldState, tick_result: TickResult) -> bool:
        if _tick_has_productive_action(tick_result):
            streak[0] = 0
            return False
        streak[0] += 1
        if streak[0] >= max_idle_ticks:
            logger.info(
                "Early stop: no productive actions for %d ticks at tick %d",
                max_idle_ticks,
                tick_num,
            )
            return True
        return False

    return _check


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentSummary:
    """Per-agent outcome for an episode."""

    agent_id: str
    agent_type: str
    final_credits: Millicredits
    final_inventory: dict[str, int]
    final_net_worth: Millicredits
    lifetime: int
    total_trades: int
    total_messages: int
    cause_of_death: str | None
    prompt_document_at_death: str | None


@dataclass(frozen=True)
class EpisodeMetrics:
    """Aggregate statistics for a completed episode."""

    ticks_executed: int
    mean_lifetime: float
    max_lifetime: int
    mean_net_worth: float
    max_net_worth: Millicredits
    total_trades: int
    total_deaths: int
    final_gini: float
    final_treasury: Millicredits
    final_agents_alive: int


@dataclass
class EpisodeResult:
    """Complete outcome of a simulation episode."""

    config: SimulationConfig
    final_world_state: WorldState
    tick_metrics: list[TickMetrics]
    agent_summaries: list[AgentSummary]
    episode_metrics: EpisodeMetrics


# ---------------------------------------------------------------------------
# Agent tracking
# ---------------------------------------------------------------------------


def _agent_type_label(agent: BaseAgent) -> str:
    """Return a descriptive type label for an agent.

    Uses ``agent_type_label`` if set (e.g. ``"llm:haiku"``),
    otherwise falls back to the class name.
    """
    return getattr(agent, "agent_type_label", type(agent).__name__)


@dataclass
class _AgentRecord:
    """Internal record tracking an agent through its lifetime."""

    agent_id: str
    agent_type: str
    agent: BaseAgent
    spawn_tick: int
    death_tick: int | None = None
    cause_of_death: str | None = None
    prompt_at_death: str | None = None
    trades: int = 0
    messages: int = 0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_episode(
    config: SimulationConfig,
    agent_factory: AgentFactory,
    *,
    output_dir: Path | None = None,
    enable_logging: bool = True,
    tick_callback: Callable[[int, float], None] | None = None,
    stop_condition: StopCondition | None = None,
) -> EpisodeResult:
    """Execute a complete simulation episode.

    Args:
        config: Simulation configuration.
        agent_factory: Factory for creating agent instances.
        output_dir: Directory for checkpoints and logs. None disables file output.
        enable_logging: Whether to enable SQLite event logging.
        tick_callback: Optional callback(tick_num, wall_seconds) called after each tick.
        stop_condition: Optional callback(tick_num, world, tick_result) that returns
            True to stop the simulation early. Called after each tick.

    Returns:
        EpisodeResult with final state, metrics, and agent summaries.
    """
    world_config = config.to_world_config()
    world = generate_world(world_config, seed=config.seed)

    # Set up output directory
    checkpoint_dir: Path | None = None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_dir = output_dir / "checkpoints"
        checkpoint_dir.mkdir(exist_ok=True)
        # Save config
        with open(output_dir / "config.json", "w") as f:
            json.dump(config.to_json(), f, indent=2)

    # Set up event logger
    db_path = output_dir / "episode.sqlite" if output_dir is not None else None
    event_logger = EventLogger(db_path, enabled=enable_logging and db_path is not None)

    # Register initial agents
    registry: dict[str, _AgentRecord] = {}
    for agent_id in world.agents:
        agent = agent_factory.create_agent(agent_id)
        agent.on_spawn(agent_id, config)
        agent_type = _agent_type_label(agent)
        registry[agent_id] = _AgentRecord(
            agent_id=agent_id,
            agent_type=agent_type,
            agent=agent,
            spawn_tick=0,
        )

    # Build the decision function — async parallel for LLM agents, sync otherwise
    has_llm_agents = _has_llm_agents(registry)
    aio_session: aiohttp.ClientSession | None = None

    def agent_decisions(
        observations: dict[str, AgentObservation],
    ) -> dict[str, AgentTurnResult]:
        nonlocal aio_session
        if has_llm_agents:
            return _run_async_decisions(observations, registry, aio_session)
        return _run_sync_decisions(observations, registry)

    # Main tick loop
    tick_metrics_list: list[TickMetrics] = []

    try:
        for tick_num in range(config.ticks_per_episode):
            # Check if all agents are dead
            alive_count = sum(1 for a in world.agents.values() if a.alive)
            if alive_count == 0:
                logger.info("All agents dead at tick %d, terminating early", tick_num)
                break

            # Expire old orders to keep order book bounded
            _expire_old_orders(world, tick_num)

            # Execute tick
            tick_start = time.monotonic()
            tick_result = execute_tick(
                world,
                agent_decisions,
                debug=config.verify_invariant_every_phase,
            )
            tick_wall_time = time.monotonic() - tick_start
            tick_metrics_list.append(tick_result.metrics)

            if tick_callback is not None:
                tick_callback(tick_num, tick_wall_time)

            # Track agent stats from action results
            for ar in tick_result.action_results:
                record = registry.get(ar.agent_id)
                if record is None:
                    continue
                if ar.success and ar.action.action_type in (
                    "accept_order",
                    "accept_trade",
                ):
                    record.trades += 1
                if ar.success and ar.action.action_type == "send_message":
                    record.messages += 1

            # Track deaths
            for dr in tick_result.death_results:
                record = registry.get(dr.agent_id)
                if record is not None:
                    record.death_tick = tick_num
                    record.cause_of_death = "tax_insolvency"
                    agent_state = world.agents.get(dr.agent_id)
                    if agent_state is not None:
                        record.prompt_at_death = agent_state.prompt_document

            # Register newly spawned agents
            for sr in tick_result.spawn_results:
                if sr.agent_id not in registry:
                    agent = agent_factory.create_agent(sr.agent_id)
                    agent.on_spawn(sr.agent_id, config)
                    agent_type = _agent_type_label(agent)
                    registry[sr.agent_id] = _AgentRecord(
                        agent_id=sr.agent_id,
                        agent_type=agent_type,
                        agent=agent,
                        spawn_tick=tick_num,
                    )

            # Log events
            event_logger.log_tick(tick_num, tick_result.metrics)
            event_logger.log_actions(tick_num, tick_result.action_results)
            event_logger.log_trades(tick_num, tick_result.action_results)
            event_logger.log_deaths(tick_num, tick_result.death_results)
            event_logger.log_messages(tick_num, tick_result.action_results)
            event_logger.log_agent_snapshots(tick_num, world)
            event_logger.log_npc_snapshots(tick_num, world)
            event_logger.flush_tick()

            # Incremental result summary (so viz can read mid-run)
            if output_dir is not None:
                _save_incremental_result(world, registry, tick_metrics_list, output_dir)

            # Checkpoint
            if (
                config.checkpoint_interval > 0
                and checkpoint_dir is not None
                and (tick_num + 1) % config.checkpoint_interval == 0
            ):
                _save_checkpoint(world, registry, checkpoint_dir, tick_num)

            # Check stop condition after logging (so partial results are captured)
            if stop_condition is not None and stop_condition(
                tick_num, world, tick_result
            ):
                if checkpoint_dir is not None:
                    _save_checkpoint(world, registry, checkpoint_dir, tick_num)
                break

    except KeyboardInterrupt:
        tick_num = max(0, len(tick_metrics_list) - 1)
        logger.info(
            "Interrupted at tick %d, saving partial results...",
            tick_num,
        )
        if checkpoint_dir is not None:
            _save_checkpoint(world, registry, checkpoint_dir, tick_num)

    event_logger.close()

    # Build results
    ticks_executed = len(tick_metrics_list)
    agent_summaries = _build_agent_summaries(world, registry, ticks_executed)
    episode_metrics = _compute_episode_metrics(
        world, tick_metrics_list, agent_summaries, ticks_executed
    )

    result = EpisodeResult(
        config=config,
        final_world_state=world,
        tick_metrics=tick_metrics_list,
        agent_summaries=agent_summaries,
        episode_metrics=episode_metrics,
    )

    # Save result summary
    if output_dir is not None:
        _save_result_summary(result, output_dir)

    return result


# ---------------------------------------------------------------------------
# Checkpointing
# ---------------------------------------------------------------------------


def _save_checkpoint(
    world: WorldState,
    registry: dict[str, _AgentRecord],
    checkpoint_dir: Path,
    tick: int,
) -> None:
    """Save a checkpoint at the given tick."""
    checkpoint = {
        "world_state": world.to_json(),
        "agent_registry": {
            agent_id: {
                "agent_type": rec.agent_type,
                "spawn_tick": rec.spawn_tick,
                "death_tick": rec.death_tick,
                "cause_of_death": rec.cause_of_death,
                "trades": rec.trades,
                "messages": rec.messages,
                "agent_state": rec.agent.get_state(),
            }
            for agent_id, rec in registry.items()
        },
    }
    path = checkpoint_dir / f"checkpoint_tick_{tick:04d}.json"
    with open(path, "w") as f:
        json.dump(checkpoint, f)
    logger.info("Checkpoint saved at tick %d", tick)


def resume_from_checkpoint(
    checkpoint_path: Path,
    config: SimulationConfig,
    agent_factory: AgentFactory,
    *,
    output_dir: Path | None = None,
    enable_logging: bool = True,
) -> EpisodeResult:
    """Resume an episode from a checkpoint file.

    Args:
        checkpoint_path: Path to checkpoint JSON file.
        config: Simulation configuration.
        agent_factory: Factory for creating agent instances.
        output_dir: Directory for checkpoints and logs.
        enable_logging: Whether to enable SQLite event logging.

    Returns:
        EpisodeResult for the remaining episode.
    """
    with open(checkpoint_path) as f:
        checkpoint = json.load(f)

    # Fix RNG state: JSON serializes tuples as lists, but Random.setstate needs tuples
    world_data = checkpoint["world_state"]
    if "rng_state" in world_data:
        state = world_data["rng_state"]
        if isinstance(state, list) and len(state) == 3:
            state[1] = tuple(state[1])
            world_data["rng_state"] = tuple(state)
    world = WorldState.from_json(world_data)
    start_tick = world.tick

    # Reconstruct agent registry
    registry: dict[str, _AgentRecord] = {}
    for agent_id, meta in checkpoint["agent_registry"].items():
        agent = agent_factory.create_agent(agent_id)
        agent.on_spawn(agent_id, config)
        # Restore agent controller state if saved in checkpoint
        saved_agent_state = meta.get("agent_state")
        if saved_agent_state is not None:
            agent.set_state(saved_agent_state)
        registry[agent_id] = _AgentRecord(
            agent_id=agent_id,
            agent_type=meta["agent_type"],
            agent=agent,
            spawn_tick=meta["spawn_tick"],
            death_tick=meta.get("death_tick"),
            cause_of_death=meta.get("cause_of_death"),
            trades=meta.get("trades", 0),
            messages=meta.get("messages", 0),
        )

    # Set up output
    checkpoint_dir: Path | None = None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_dir = output_dir / "checkpoints"
        checkpoint_dir.mkdir(exist_ok=True)

    db_path = output_dir / "episode_resumed.sqlite" if output_dir is not None else None
    event_logger = EventLogger(db_path, enabled=enable_logging and db_path is not None)

    has_llm_agents = _has_llm_agents(registry)

    def agent_decisions(
        observations: dict[str, AgentObservation],
    ) -> dict[str, AgentTurnResult]:
        if has_llm_agents:
            return _run_async_decisions(observations, registry, None)
        return _run_sync_decisions(observations, registry)

    tick_metrics_list: list[TickMetrics] = []

    for tick_num in range(start_tick, config.ticks_per_episode):
        alive_count = sum(1 for a in world.agents.values() if a.alive)
        if alive_count == 0:
            break

        _expire_old_orders(world, tick_num)

        tick_result = execute_tick(
            world, agent_decisions, debug=config.verify_invariant_every_phase
        )
        tick_metrics_list.append(tick_result.metrics)

        for ar in tick_result.action_results:
            record = registry.get(ar.agent_id)
            if record is None:
                continue
            if ar.success and ar.action.action_type in ("accept_order", "accept_trade"):
                record.trades += 1
            if ar.success and ar.action.action_type == "send_message":
                record.messages += 1

        for dr in tick_result.death_results:
            record = registry.get(dr.agent_id)
            if record is not None:
                record.death_tick = tick_num
                record.cause_of_death = "tax_insolvency"

        for sr in tick_result.spawn_results:
            if sr.agent_id not in registry:
                agent = agent_factory.create_agent(sr.agent_id)
                agent.on_spawn(sr.agent_id, config)
                registry[sr.agent_id] = _AgentRecord(
                    agent_id=sr.agent_id,
                    agent_type=_agent_type_label(agent),
                    agent=agent,
                    spawn_tick=tick_num,
                )

        event_logger.log_tick(tick_num, tick_result.metrics)
        event_logger.log_actions(tick_num, tick_result.action_results)
        event_logger.log_trades(tick_num, tick_result.action_results)
        event_logger.log_deaths(tick_num, tick_result.death_results)
        event_logger.log_messages(tick_num, tick_result.action_results)
        event_logger.log_agent_snapshots(tick_num, world)
        event_logger.log_npc_snapshots(tick_num, world)
        event_logger.flush_tick()

        if (
            config.checkpoint_interval > 0
            and checkpoint_dir is not None
            and (tick_num + 1) % config.checkpoint_interval == 0
        ):
            _save_checkpoint(world, registry, checkpoint_dir, tick_num)

    event_logger.close()

    ticks_executed = len(tick_metrics_list)
    agent_summaries = _build_agent_summaries(world, registry, ticks_executed)
    episode_metrics = _compute_episode_metrics(
        world, tick_metrics_list, agent_summaries, ticks_executed
    )

    return EpisodeResult(
        config=config,
        final_world_state=world,
        tick_metrics=tick_metrics_list,
        agent_summaries=agent_summaries,
        episode_metrics=episode_metrics,
    )


# ---------------------------------------------------------------------------
# Async / sync decision helpers
# ---------------------------------------------------------------------------


def _has_llm_agents(registry: dict[str, _AgentRecord]) -> bool:
    """Return True if any registered agent is an LLMAgent."""
    from evomarket.agents.llm_agent import LLMAgent

    return any(isinstance(rec.agent, LLMAgent) for rec in registry.values())


def _run_sync_decisions(
    observations: dict[str, AgentObservation],
    registry: dict[str, _AgentRecord],
) -> dict[str, AgentTurnResult]:
    """Serial decision loop for heuristic agents."""
    results: dict[str, AgentTurnResult] = {}
    for agent_id, obs in observations.items():
        record = registry.get(agent_id)
        if record is None:
            results[agent_id] = AgentTurnResult(action=IdleAction())
            continue
        try:
            results[agent_id] = record.agent.decide(obs)
        except Exception:
            logger.warning("Agent %s decide() failed, using idle", agent_id)
            results[agent_id] = AgentTurnResult(action=IdleAction())
    return results


def _run_async_decisions(
    observations: dict[str, AgentObservation],
    registry: dict[str, _AgentRecord],
    session: aiohttp.ClientSession | None,
) -> dict[str, AgentTurnResult]:
    """Parallel decision calls for LLM agents via asyncio.gather."""
    from evomarket.agents.llm_agent import LLMAgent

    async def _gather() -> dict[str, AgentTurnResult]:
        async with aiohttp.ClientSession() as sess:
            tasks: dict[str, asyncio.Task[AgentTurnResult]] = {}
            for agent_id, obs in observations.items():
                record = registry.get(agent_id)
                if record is None:
                    tasks[agent_id] = asyncio.ensure_future(_idle_coro(agent_id))
                elif isinstance(record.agent, LLMAgent):
                    tasks[agent_id] = asyncio.ensure_future(
                        record.agent.decide_async(obs, sess)
                    )
                else:
                    # Non-LLM agents run synchronously, wrapped in a coro
                    tasks[agent_id] = asyncio.ensure_future(
                        _sync_decide_coro(record, obs)
                    )
            await asyncio.gather(*tasks.values(), return_exceptions=True)
            results: dict[str, AgentTurnResult] = {}
            for agent_id, task in tasks.items():
                exc = task.exception() if task.done() and not task.cancelled() else None
                if exc is not None:
                    logger.warning("Agent %s async decide failed: %s", agent_id, exc)
                    results[agent_id] = AgentTurnResult(action=IdleAction())
                else:
                    results[agent_id] = task.result()
            return results

    return asyncio.run(_gather())


async def _idle_coro(agent_id: str) -> AgentTurnResult:
    """Coroutine returning an idle action (for missing agents)."""
    return AgentTurnResult(action=IdleAction())


async def _sync_decide_coro(
    record: _AgentRecord, obs: AgentObservation
) -> AgentTurnResult:
    """Wrap a synchronous decide() call in a coroutine."""
    try:
        return record.agent.decide(obs)
    except Exception:
        logger.warning("Agent %s decide() failed, using idle", record.agent_id)
        return AgentTurnResult(action=IdleAction())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _expire_old_orders(world: WorldState, current_tick: int) -> None:
    """Cancel orders older than _ORDER_EXPIRY_TICKS and prune terminal entries.

    post_order() does not escrow inventory/credits, so cancellation simply
    marks the order as cancelled. We also prune terminal orders and proposals
    to keep the dicts bounded.
    """
    from evomarket.engine.trading import OrderStatus, TradeStatus

    # Expire old active/suspended orders
    for order in world.order_book.values():
        if order.status not in (OrderStatus.ACTIVE, OrderStatus.SUSPENDED):
            continue
        if current_tick - order.created_tick >= _ORDER_EXPIRY_TICKS:
            order.status = OrderStatus.CANCELLED

    # Prune terminal orders and proposals to keep dicts small
    terminal_order_ids = [
        oid
        for oid, o in world.order_book.items()
        if o.status in (OrderStatus.CANCELLED, OrderStatus.FILLED)
    ]
    for oid in terminal_order_ids:
        del world.order_book[oid]

    terminal_proposal_ids = [
        tid
        for tid, p in world.trade_proposals.items()
        if p.status in (TradeStatus.ACCEPTED, TradeStatus.INVALID, TradeStatus.EXPIRED)
    ]
    for tid in terminal_proposal_ids:
        del world.trade_proposals[tid]


def _build_agent_summaries(
    world: WorldState,
    registry: dict[str, _AgentRecord],
    ticks_executed: int,
) -> list[AgentSummary]:
    """Build per-agent summaries from registry and final world state."""
    summaries: list[AgentSummary] = []
    for agent_id, record in registry.items():
        agent_state = world.agents.get(agent_id)
        if agent_state is None:
            continue

        # Compute net worth: credits + commodity liquidation value
        final_credits = agent_state.credits
        inv_value: Millicredits = 0
        for commodity, qty in agent_state.inventory.items():
            # Use average NPC price across nodes as liquidation estimate
            prices = [world.get_npc_price(nid, commodity) for nid in world.nodes]
            avg_price = sum(prices) // max(1, len([p for p in prices if p > 0]))
            inv_value += avg_price * qty

        lifetime = (
            record.death_tick - record.spawn_tick
            if record.death_tick is not None
            else ticks_executed - record.spawn_tick
        )

        inv_dict = {k.value: v for k, v in agent_state.inventory.items()}

        summaries.append(
            AgentSummary(
                agent_id=agent_id,
                agent_type=record.agent_type,
                final_credits=final_credits,
                final_inventory=inv_dict,
                final_net_worth=final_credits + inv_value,
                lifetime=lifetime,
                total_trades=record.trades,
                total_messages=record.messages,
                cause_of_death=record.cause_of_death,
                prompt_document_at_death=record.prompt_at_death,
            )
        )
    return summaries


def _compute_episode_metrics(
    world: WorldState,
    tick_metrics: list[TickMetrics],
    agent_summaries: list[AgentSummary],
    ticks_executed: int,
) -> EpisodeMetrics:
    """Compute aggregate episode metrics."""
    lifetimes = [s.lifetime for s in agent_summaries]
    net_worths = [s.final_net_worth for s in agent_summaries]
    total_trades = sum(s.total_trades for s in agent_summaries)
    total_deaths = sum(1 for s in agent_summaries if s.cause_of_death is not None)

    final_gini = tick_metrics[-1].agent_credit_gini if tick_metrics else 0.0

    return EpisodeMetrics(
        ticks_executed=ticks_executed,
        mean_lifetime=sum(lifetimes) / max(1, len(lifetimes)),
        max_lifetime=max(lifetimes) if lifetimes else 0,
        mean_net_worth=sum(net_worths) / max(1, len(net_worths)),
        max_net_worth=max(net_worths) if net_worths else 0,
        total_trades=total_trades,
        total_deaths=total_deaths,
        final_gini=final_gini,
        final_treasury=world.treasury,
        final_agents_alive=sum(1 for a in world.agents.values() if a.alive),
    )


def _save_incremental_result(
    world: WorldState,
    registry: dict[str, _AgentRecord],
    tick_metrics_list: list[TickMetrics],
    output_dir: Path,
) -> None:
    """Write a partial result.json so visualization can read mid-run."""
    ticks_executed = len(tick_metrics_list)
    agent_summaries = _build_agent_summaries(world, registry, ticks_executed)
    episode_metrics = _compute_episode_metrics(
        world, tick_metrics_list, agent_summaries, ticks_executed
    )
    result = EpisodeResult(
        config=None,  # type: ignore[arg-type]
        final_world_state=world,
        tick_metrics=tick_metrics_list,
        agent_summaries=agent_summaries,
        episode_metrics=episode_metrics,
    )
    _save_result_summary(result, output_dir)


def _save_result_summary(result: EpisodeResult, output_dir: Path) -> None:
    """Save a JSON summary of the episode result."""
    summary = {
        "ticks_executed": result.episode_metrics.ticks_executed,
        "mean_lifetime": result.episode_metrics.mean_lifetime,
        "max_lifetime": result.episode_metrics.max_lifetime,
        "mean_net_worth": to_display_credits(result.episode_metrics.mean_net_worth),
        "max_net_worth": to_display_credits(result.episode_metrics.max_net_worth),
        "total_trades": result.episode_metrics.total_trades,
        "total_deaths": result.episode_metrics.total_deaths,
        "final_gini": result.episode_metrics.final_gini,
        "final_treasury": to_display_credits(result.episode_metrics.final_treasury),
        "final_agents_alive": result.episode_metrics.final_agents_alive,
        "agent_summaries": [
            {
                "agent_id": s.agent_id,
                "agent_type": s.agent_type,
                "final_credits": to_display_credits(s.final_credits),
                "final_net_worth": to_display_credits(s.final_net_worth),
                "lifetime": s.lifetime,
                "total_trades": s.total_trades,
                "cause_of_death": s.cause_of_death,
            }
            for s in result.agent_summaries
        ],
    }
    with open(output_dir / "result.json", "w") as f:
        json.dump(summary, f, indent=2)
