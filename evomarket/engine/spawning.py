"""Agent spawning — create replacement agents funded from treasury."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from evomarket.core.agent import Agent
from evomarket.core.types import CommodityType, Millicredits, NodeType
from evomarket.engine.economy import fund_spawn

if TYPE_CHECKING:
    from evomarket.core.world import WorldState


@dataclass(frozen=True)
class SpawnResult:
    """Record of a single agent spawn."""

    agent_id: str
    location: str
    starting_credits: Millicredits


def spawn_agents(world: WorldState) -> list[SpawnResult]:
    """Spawn replacement agents up to population target.

    Stops if treasury cannot fund a spawn.
    """
    alive_count = sum(1 for a in world.agents.values() if a.alive)
    needed = world.config.population_size - alive_count

    if needed <= 0:
        return []

    # Find spawn nodes
    spawn_nodes = [n for n in world.nodes.values() if n.node_type == NodeType.SPAWN]
    if not spawn_nodes:
        # Fallback: use any node
        spawn_nodes = list(world.nodes.values())

    # Get commodity types in use (from any agent's inventory keys)
    commodity_types: list[CommodityType] = []
    for agent in world.agents.values():
        commodity_types = list(agent.inventory.keys())
        break
    if not commodity_types:
        commodity_types = list(CommodityType)

    results: list[SpawnResult] = []

    for _ in range(needed):
        if not fund_spawn(world, world.config.starting_credits):
            break

        agent_id = f"agent_{world.next_agent_id:03d}"
        location = world.rng.choice(spawn_nodes).node_id

        agent = Agent(
            agent_id=agent_id,
            display_name=f"Agent {world.next_agent_id}",
            location=location,
            credits=world.config.starting_credits,
            inventory={c: 0 for c in commodity_types},
            age=0,
            alive=True,
            will={},
            prompt_document="",
            grace_ticks_remaining=world.config.spawn_grace_period,
        )
        world.agents[agent_id] = agent
        world.next_agent_id += 1

        results.append(
            SpawnResult(
                agent_id=agent_id,
                location=location,
                starting_credits=world.config.starting_credits,
            )
        )

    return results
