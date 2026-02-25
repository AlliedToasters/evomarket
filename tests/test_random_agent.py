"""Tests for RandomAgent."""

from evomarket.agents.random_agent import RandomAgent, RandomAgentFactory
from evomarket.core.types import CommodityType
from evomarket.engine.observation import (
    AgentObservation,
    AgentPublicView,
    AgentStateView,
    NodeView,
    OrderView,
    PreambleData,
)
from evomarket.simulation.config import SimulationConfig


def _make_observation(
    *,
    node_type: str = "RESOURCE",
    credits: int = 30_000,
    inventory: dict[CommodityType, int] | None = None,
    adjacent: list[str] | None = None,
    resource_avail: dict[CommodityType, int] | None = None,
    agents_present: list[AgentPublicView] | None = None,
    orders: list[OrderView] | None = None,
) -> AgentObservation:
    if inventory is None:
        inventory = {CommodityType.IRON: 0}
    if adjacent is None:
        adjacent = ["node_a", "node_b"]
    if resource_avail is None:
        resource_avail = {CommodityType.IRON: 5}
    return AgentObservation(
        preamble=PreambleData(tick=0),
        prompt_document="",
        agent_state=AgentStateView(
            location="node_test",
            credits=credits,
            inventory=inventory,
            age=1,
            grace_ticks_remaining=0,
        ),
        node_info=NodeView(
            node_id="node_test",
            name="Test",
            node_type=node_type,
            adjacent_nodes=adjacent,
            adjacent_node_info=[],
            npc_prices={CommodityType.IRON: 5000},
            resource_availability=resource_avail,
        ),
        agents_present=agents_present or [],
        posted_orders=orders or [],
        messages_received=[],
        pending_proposals=[],
        own_orders=[],
        own_pending_proposals=[],
        own_will={},
    )


class TestRandomAgent:
    def test_returns_valid_action(self) -> None:
        agent = RandomAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_observation()
        result = agent.decide(obs)
        assert result.action is not None

    def test_at_resource_node_can_harvest(self) -> None:
        """Over many tries, random agent should sometimes harvest at resource nodes."""
        agent = RandomAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_observation(node_type="RESOURCE")
        actions = {agent.decide(obs).action.action_type for _ in range(50)}
        assert "harvest" in actions

    def test_can_move(self) -> None:
        agent = RandomAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_observation()
        actions = {agent.decide(obs).action.action_type for _ in range(50)}
        assert "move" in actions

    def test_deterministic_with_same_seed(self) -> None:
        obs = _make_observation()
        agent1 = RandomAgent(seed=123)
        agent1.on_spawn("agent_001", SimulationConfig())
        agent2 = RandomAgent(seed=123)
        agent2.on_spawn("agent_001", SimulationConfig())

        for _ in range(20):
            r1 = agent1.decide(obs)
            r2 = agent2.decide(obs)
            assert r1.action.action_type == r2.action.action_type


class TestRandomAgentFactory:
    def test_creates_agents(self) -> None:
        factory = RandomAgentFactory(base_seed=42)
        factory.set_config(SimulationConfig())
        agent = factory.create_agent("agent_001")
        assert isinstance(agent, RandomAgent)

    def test_deterministic_seeds(self) -> None:
        factory1 = RandomAgentFactory(base_seed=42)
        factory1.set_config(SimulationConfig())
        factory2 = RandomAgentFactory(base_seed=42)
        factory2.set_config(SimulationConfig())

        obs = _make_observation()
        a1 = factory1.create_agent("agent_001")
        a2 = factory2.create_agent("agent_001")

        for _ in range(10):
            assert (
                a1.decide(obs).action.action_type == a2.decide(obs).action.action_type
            )
