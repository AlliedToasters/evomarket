"""Heuristic agents — five strategy archetypes for Phase 0 validation."""

from __future__ import annotations

import random
from collections import defaultdict
from enum import Enum

from evomarket.agents.base import AgentFactory, BaseAgent
from evomarket.core.types import CommodityType, Millicredits
from evomarket.engine.actions import (
    AcceptOrderAction,
    AcceptTradeAction,
    Action,
    AgentTurnResult,
    HarvestAction,
    IdleAction,
    InspectAction,
    MoveAction,
    PostOrderAction,
    ProposeTradeAction,
    SendMessageAction,
    UpdateWillAction,
)
from evomarket.engine.observation import AgentObservation
from evomarket.simulation.config import SimulationConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _best_adjacent_for(
    obs: AgentObservation,
    target_type: str,
    rng: random.Random,
) -> str | None:
    """Pick an adjacent node of the given type, or the first adjacent if none match."""
    # We don't have full graph info, just adjacent node IDs and current node type.
    # Simple heuristic: pick a random adjacent node (agents will explore).
    if obs.node_info.adjacent_nodes:
        return rng.choice(obs.node_info.adjacent_nodes)
    return None


def _has_inventory(obs: AgentObservation) -> bool:
    return any(qty > 0 for qty in obs.agent_state.inventory.values())


def _total_inventory(obs: AgentObservation) -> int:
    return sum(obs.agent_state.inventory.values())


def _best_commodity_to_sell(obs: AgentObservation) -> CommodityType | None:
    """Return the commodity with highest NPC price that we have in inventory."""
    best: CommodityType | None = None
    best_value: Millicredits = 0
    for commodity, qty in obs.agent_state.inventory.items():
        if qty <= 0:
            continue
        npc_price = obs.node_info.npc_prices.get(commodity, 0)
        if npc_price > best_value:
            best_value = npc_price
            best = commodity
    return best


# ---------------------------------------------------------------------------
# HarvesterAgent
# ---------------------------------------------------------------------------


class HarvesterState(str, Enum):
    MOVE_TO_RESOURCE = "MOVE_TO_RESOURCE"
    HARVEST = "HARVEST"
    MOVE_TO_HUB = "MOVE_TO_HUB"
    SELL = "SELL"


class HarvesterAgent(BaseAgent):
    """Harvests resources and sells to NPCs. Simple gather-sell loop."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._agent_id: str = ""
        self._state = HarvesterState.MOVE_TO_RESOURCE
        self._ticks_in_state: int = 0

    def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
        self._agent_id = agent_id

    def decide(self, obs: AgentObservation) -> AgentTurnResult:
        self._ticks_in_state += 1
        action = self._pick_action(obs)
        return AgentTurnResult(action=action)

    def _pick_action(self, obs: AgentObservation) -> Action:
        # State machine transitions
        if self._state == HarvesterState.MOVE_TO_RESOURCE:
            if obs.node_info.node_type == "RESOURCE" and any(
                qty > 0 for qty in obs.node_info.resource_availability.values()
            ):
                self._transition(HarvesterState.HARVEST)
                return HarvestAction()
            return self._move_toward_type(obs, "RESOURCE")

        elif self._state == HarvesterState.HARVEST:
            if _total_inventory(obs) >= 5 or not any(
                qty > 0 for qty in obs.node_info.resource_availability.values()
            ):
                self._transition(HarvesterState.MOVE_TO_HUB)
                return self._move_toward_type(obs, "TRADE_HUB")
            return HarvestAction()

        elif self._state == HarvesterState.MOVE_TO_HUB:
            if obs.node_info.node_type == "TRADE_HUB":
                self._transition(HarvesterState.SELL)
                return self._sell_action(obs)
            return self._move_toward_type(obs, "TRADE_HUB")

        elif self._state == HarvesterState.SELL:
            if not _has_inventory(obs):
                self._transition(HarvesterState.MOVE_TO_RESOURCE)
                return self._move_toward_type(obs, "RESOURCE")
            return self._sell_action(obs)

        return IdleAction()

    def _transition(self, new_state: HarvesterState) -> None:
        self._state = new_state
        self._ticks_in_state = 0

    def _move_toward_type(self, obs: AgentObservation, target_type: str) -> Action:
        node = _best_adjacent_for(obs, target_type, self._rng)
        if node is not None:
            return MoveAction(target_node=node)
        return IdleAction()

    def _sell_action(self, obs: AgentObservation) -> Action:
        for commodity, qty in obs.agent_state.inventory.items():
            if qty > 0:
                # Price at 80% of NPC price to ensure fill
                npc_price = obs.node_info.npc_prices.get(commodity, 3000)
                price = max(1, npc_price * 80 // 100)
                return PostOrderAction(
                    side="sell", commodity=commodity, quantity=qty, price=price
                )
        return IdleAction()


# ---------------------------------------------------------------------------
# TraderAgent
# ---------------------------------------------------------------------------


class TraderAgent(BaseAgent):
    """Exploits spatial price differentials — buy low, move, sell high."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._agent_id: str = ""
        self._price_memory: dict[str, dict[CommodityType, Millicredits]] = defaultdict(
            dict
        )
        self._ticks_at_node: int = 0

    def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
        self._agent_id = agent_id

    def decide(self, obs: AgentObservation) -> AgentTurnResult:
        # Record prices at current node
        for commodity, price in obs.node_info.npc_prices.items():
            self._price_memory[obs.node_info.node_id][commodity] = price
        self._ticks_at_node += 1

        action = self._pick_action(obs)
        return AgentTurnResult(action=action)

    def _pick_action(self, obs: AgentObservation) -> Action:
        # If we have inventory and good NPC prices here, sell
        if _has_inventory(obs):
            commodity = _best_commodity_to_sell(obs)
            if commodity is not None:
                qty = obs.agent_state.inventory[commodity]
                npc_price = obs.node_info.npc_prices.get(commodity, 3000)
                if npc_price > 2000:
                    return PostOrderAction(
                        side="sell",
                        commodity=commodity,
                        quantity=qty,
                        price=max(1, npc_price * 90 // 100),
                    )

        # If we have credits and prices are low, buy
        if obs.agent_state.credits > 5000 and obs.node_info.npc_prices:
            cheapest: CommodityType | None = None
            cheapest_price: Millicredits = 999999999
            for commodity, price in obs.node_info.npc_prices.items():
                if 0 < price < cheapest_price:
                    cheapest_price = price
                    cheapest = commodity
            # Accept posted sell orders that are below NPC price
            for order in obs.posted_orders:
                if (
                    order.poster_id != self._agent_id
                    and order.side == "sell"
                    and order.price_per_unit * order.quantity <= obs.agent_state.credits
                ):
                    npc_price = obs.node_info.npc_prices.get(order.commodity, 0)
                    if order.price_per_unit < npc_price:
                        return AcceptOrderAction(order_id=order.order_id)

            if cheapest is not None and cheapest_price < 4000:
                return PostOrderAction(
                    side="buy",
                    commodity=cheapest,
                    quantity=1,
                    price=cheapest_price,
                )

        # Move after a few ticks
        if self._ticks_at_node >= 2:
            self._ticks_at_node = 0
            node = _best_adjacent_for(obs, "TRADE_HUB", self._rng)
            if node is not None:
                return MoveAction(target_node=node)

        return IdleAction()


# ---------------------------------------------------------------------------
# SocialAgent
# ---------------------------------------------------------------------------


class SocialAgent(BaseAgent):
    """Focuses on P2P trading and social interaction."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._agent_id: str = ""
        self._ticks_at_node: int = 0

    def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
        self._agent_id = agent_id

    def decide(self, obs: AgentObservation) -> AgentTurnResult:
        self._ticks_at_node += 1
        action = self._pick_action(obs)
        return AgentTurnResult(action=action)

    def _pick_action(self, obs: AgentObservation) -> Action:
        # Accept incoming trade proposals that give us credits
        for proposal in obs.pending_proposals:
            if proposal.offer_credits > 0:
                return AcceptTradeAction(trade_id=proposal.trade_id)

        # Accept orders at current node
        for order in obs.posted_orders:
            if order.poster_id == self._agent_id:
                continue
            if (
                order.side == "sell"
                and obs.agent_state.credits >= order.price_per_unit * order.quantity
            ):
                return AcceptOrderAction(order_id=order.order_id)

        # Post sell orders for our inventory
        if _has_inventory(obs):
            for commodity, qty in obs.agent_state.inventory.items():
                if qty > 0:
                    npc_price = obs.node_info.npc_prices.get(commodity, 3000)
                    # Price slightly above NPC to attract P2P
                    price = max(1, npc_price * 110 // 100)
                    return PostOrderAction(
                        side="sell", commodity=commodity, quantity=qty, price=price
                    )

        # Propose trades to nearby agents
        if obs.agents_present and _has_inventory(obs):
            target = self._rng.choice(obs.agents_present)
            # Offer a commodity, request credits
            for commodity, qty in obs.agent_state.inventory.items():
                if qty > 0:
                    return ProposeTradeAction(
                        target_agent=target.agent_id,
                        offer={commodity.value: 1},
                        request={"credits": 3000},
                    )

        # Move to busier nodes periodically
        if self._ticks_at_node >= 4 and len(obs.agents_present) < 2:
            self._ticks_at_node = 0
            node = _best_adjacent_for(obs, "TRADE_HUB", self._rng)
            if node is not None:
                return MoveAction(target_node=node)

        # Harvest if at resource node with nothing else to do
        if obs.node_info.node_type == "RESOURCE" and any(
            qty > 0 for qty in obs.node_info.resource_availability.values()
        ):
            return HarvestAction()

        return IdleAction()


# ---------------------------------------------------------------------------
# HoarderAgent
# ---------------------------------------------------------------------------


class HoarderAgent(BaseAgent):
    """Accumulates resources, rarely trades, updates will."""

    TAX_PANIC_THRESHOLD: int = 3000  # millicredits (3 credits)

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._agent_id: str = ""

    def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
        self._agent_id = agent_id

    def decide(self, obs: AgentObservation) -> AgentTurnResult:
        action = self._pick_action(obs)
        return AgentTurnResult(action=action)

    def _pick_action(self, obs: AgentObservation) -> Action:
        # Emergency sell if credits are dangerously low
        if obs.agent_state.credits < self.TAX_PANIC_THRESHOLD and _has_inventory(obs):
            commodity = _best_commodity_to_sell(obs)
            if commodity is not None:
                qty = obs.agent_state.inventory[commodity]
                npc_price = obs.node_info.npc_prices.get(commodity, 3000)
                return PostOrderAction(
                    side="sell",
                    commodity=commodity,
                    quantity=min(2, qty),  # Sell only what's needed
                    price=max(1, npc_price * 70 // 100),  # Discount for fast fill
                )

        # Update will with nearby agents
        if obs.agents_present and self._rng.random() < 0.2:
            beneficiaries = {
                a.agent_id: 1.0 / len(obs.agents_present)
                for a in obs.agents_present[:3]
            }
            total = sum(beneficiaries.values())
            if total > 1.0:
                beneficiaries = {k: v / total for k, v in beneficiaries.items()}
            return UpdateWillAction(distribution=beneficiaries)

        # Harvest if at resource node
        if obs.node_info.node_type == "RESOURCE" and any(
            qty > 0 for qty in obs.node_info.resource_availability.values()
        ):
            return HarvestAction()

        # Move to resource nodes
        if obs.node_info.node_type != "RESOURCE":
            node = _best_adjacent_for(obs, "RESOURCE", self._rng)
            if node is not None:
                return MoveAction(target_node=node)

        return IdleAction()


# ---------------------------------------------------------------------------
# ExplorerAgent
# ---------------------------------------------------------------------------


class ExplorerAgent(BaseAgent):
    """Moves frequently, inspects agents, broadcasts observations."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self._agent_id: str = ""
        self._ticks_at_node: int = 0

    def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
        self._agent_id = agent_id

    def decide(self, obs: AgentObservation) -> AgentTurnResult:
        self._ticks_at_node += 1
        action = self._pick_action(obs)
        return AgentTurnResult(action=action)

    def _pick_action(self, obs: AgentObservation) -> Action:
        # Move after 1-2 ticks
        if self._ticks_at_node >= self._rng.randint(1, 2):
            self._ticks_at_node = 0
            if obs.node_info.adjacent_nodes:
                target = self._rng.choice(obs.node_info.adjacent_nodes)
                return MoveAction(target_node=target)

        # Inspect a nearby agent
        if obs.agents_present:
            target = self._rng.choice(obs.agents_present)
            return InspectAction(target_agent=target.agent_id)

        # Broadcast about local conditions
        if self._rng.random() < 0.3:
            prices_info = ", ".join(
                f"{c.value}={p}" for c, p in obs.node_info.npc_prices.items()
            )
            text = f"Node {obs.node_info.node_id}: prices=[{prices_info}]"
            return SendMessageAction(target="broadcast", text=text[:500])

        # Harvest opportunistically
        if obs.node_info.node_type == "RESOURCE" and any(
            qty > 0 for qty in obs.node_info.resource_availability.values()
        ):
            return HarvestAction()

        # Sell if carrying items
        if _has_inventory(obs):
            commodity = _best_commodity_to_sell(obs)
            if commodity is not None:
                qty = obs.agent_state.inventory[commodity]
                npc_price = obs.node_info.npc_prices.get(commodity, 3000)
                return PostOrderAction(
                    side="sell",
                    commodity=commodity,
                    quantity=qty,
                    price=max(1, npc_price * 85 // 100),
                )

        return IdleAction()


# ---------------------------------------------------------------------------
# HeuristicAgentFactory
# ---------------------------------------------------------------------------

_AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    "harvester": HarvesterAgent,
    "trader": TraderAgent,
    "social": SocialAgent,
    "hoarder": HoarderAgent,
    "explorer": ExplorerAgent,
}


class HeuristicAgentFactory(AgentFactory):
    """Creates agents based on agent_mix config, distributing types round-robin."""

    def __init__(self, config: SimulationConfig) -> None:
        self._config = config
        self._base_seed = config.seed
        # Build the round-robin sequence
        self._type_sequence: list[str] = []
        for agent_type, count in config.agent_mix.items():
            self._type_sequence.extend([agent_type] * count)
        self._next_index = 0

    def create_agent(self, agent_id: str) -> BaseAgent:
        # Pick the next type in round-robin
        if self._next_index < len(self._type_sequence):
            agent_type = self._type_sequence[self._next_index]
        else:
            # Wrap around for respawned agents
            agent_type = self._type_sequence[
                self._next_index % len(self._type_sequence)
            ]
        self._next_index += 1

        seed = hash((self._base_seed, agent_id)) & 0xFFFFFFFF
        agent_cls = _AGENT_CLASSES.get(agent_type)
        if agent_cls is None:
            # Fallback: random-ish idle agent using HarvesterAgent
            agent_cls = HarvesterAgent

        agent = agent_cls(seed=seed)
        agent.on_spawn(agent_id, self._config)
        return agent
