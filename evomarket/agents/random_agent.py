"""Random agent — uniformly random valid action selection."""

from __future__ import annotations

import random

from evomarket.agents.base import AgentFactory, BaseAgent
from evomarket.core.types import CommodityType
from evomarket.engine.actions import (
    Action,
    AgentTurnResult,
    HarvestAction,
    IdleAction,
    InspectAction,
    MoveAction,
    PostOrderAction,
    SendMessageAction,
)
from evomarket.engine.observation import AgentObservation
from evomarket.simulation.config import SimulationConfig


class RandomAgent(BaseAgent):
    """Selects a uniformly random valid action each tick."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._agent_id: str = ""
        self._config: SimulationConfig | None = None

    def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
        self._agent_id = agent_id
        self._config = config

    def decide(self, observation: AgentObservation) -> AgentTurnResult:
        candidates = self._get_valid_actions(observation)
        action = self._rng.choice(candidates)
        return AgentTurnResult(action=action)

    def _get_valid_actions(self, obs: AgentObservation) -> list[Action]:
        actions: list[Action] = [IdleAction()]

        # Move to adjacent nodes
        for node_id in obs.node_info.adjacent_nodes:
            actions.append(MoveAction(target_node=node_id))

        # Harvest if at resource node with resources
        if obs.node_info.node_type == "RESOURCE":
            if any(qty > 0 for qty in obs.node_info.resource_availability.values()):
                actions.append(HarvestAction())

        # Post sell orders for inventory items
        for commodity, qty in obs.agent_state.inventory.items():
            if qty > 0:
                price = self._rng.randint(1000, 10000)
                actions.append(
                    PostOrderAction(
                        side="sell",
                        commodity=commodity,
                        quantity=min(qty, self._rng.randint(1, max(1, qty))),
                        price=price,
                    )
                )

        # Post buy orders if we have credits
        if obs.agent_state.credits > 2000:
            commodity = self._rng.choice(list(CommodityType))
            price = self._rng.randint(1000, 5000)
            actions.append(
                PostOrderAction(
                    side="buy",
                    commodity=commodity,
                    quantity=1,
                    price=price,
                )
            )

        # Accept existing orders
        for order in obs.posted_orders:
            if order.poster_id != self._agent_id:
                from evomarket.engine.actions import AcceptOrderAction

                actions.append(AcceptOrderAction(order_id=order.order_id))

        # Accept incoming trade proposals
        for proposal in obs.pending_proposals:
            from evomarket.engine.actions import AcceptTradeAction

            actions.append(AcceptTradeAction(trade_id=proposal.trade_id))

        # Inspect agents present
        for agent in obs.agents_present:
            actions.append(InspectAction(target_agent=agent.agent_id))

        # Send message to an agent present
        if obs.agents_present:
            target = self._rng.choice(obs.agents_present)
            actions.append(SendMessageAction(target=target.agent_id, text="hello"))

        return actions


class RandomAgentFactory(AgentFactory):
    """Creates RandomAgent instances with deterministic per-agent seeds."""

    def __init__(self, base_seed: int = 42) -> None:
        self._base_seed = base_seed
        self._config: SimulationConfig | None = None

    def set_config(self, config: SimulationConfig) -> None:
        """Set the simulation config to pass to agents on spawn."""
        self._config = config

    def create_agent(self, agent_id: str) -> BaseAgent:
        seed = hash((self._base_seed, agent_id)) & 0xFFFFFFFF
        agent = RandomAgent(seed=seed)
        if self._config is not None:
            agent.on_spawn(agent_id, self._config)
        return agent
