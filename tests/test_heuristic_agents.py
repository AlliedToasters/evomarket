"""Tests for heuristic agents."""

from evomarket.agents.heuristic_agent import (
    ExplorerAgent,
    HarvesterAgent,
    HeuristicAgentFactory,
    HoarderAgent,
    SocialAgent,
    TraderAgent,
)
from evomarket.core.types import CommodityType
from evomarket.engine.observation import (
    AgentObservation,
    AgentPublicView,
    AgentStateView,
    NodeView,
    OrderView,
    PreambleData,
    TradeProposalView,
)
from evomarket.simulation.config import SimulationConfig


def _make_obs(
    *,
    node_type: str = "RESOURCE",
    credits: int = 30_000,
    inventory: dict[CommodityType, int] | None = None,
    adjacent: list[str] | None = None,
    resource_avail: dict[CommodityType, int] | None = None,
    agents_present: list[AgentPublicView] | None = None,
    npc_prices: dict[CommodityType, int] | None = None,
    posted_orders: list[OrderView] | None = None,
    pending_proposals: list[TradeProposalView] | None = None,
) -> AgentObservation:
    if inventory is None:
        inventory = {CommodityType.IRON: 0}
    if adjacent is None:
        adjacent = ["node_hub_iron", "node_iron_1"]
    if resource_avail is None:
        resource_avail = {CommodityType.IRON: 5}
    if npc_prices is None:
        npc_prices = {CommodityType.IRON: 5000}
    return AgentObservation(
        preamble=PreambleData(tick=10),
        prompt_document="",
        agent_state=AgentStateView(
            location="node_test",
            credits=credits,
            inventory=inventory,
            age=10,
            grace_ticks_remaining=0,
        ),
        node_info=NodeView(
            node_id="node_test",
            name="Test",
            node_type=node_type,
            adjacent_nodes=adjacent,
            npc_prices=npc_prices,
            resource_availability=resource_avail,
        ),
        agents_present=agents_present or [],
        posted_orders=posted_orders or [],
        messages_received=[],
        pending_proposals=pending_proposals or [],
        own_orders=[],
        own_pending_proposals=[],
        own_will={},
    )


class TestHarvesterAgent:
    def test_harvests_at_resource_node(self) -> None:
        agent = HarvesterAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_obs(node_type="RESOURCE")
        result = agent.decide(obs)
        assert result.action.action_type == "harvest"

    def test_moves_when_not_at_resource(self) -> None:
        agent = HarvesterAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_obs(node_type="TRADE_HUB", resource_avail={})
        result = agent.decide(obs)
        assert result.action.action_type == "move"

    def test_sells_at_hub_with_inventory(self) -> None:
        agent = HarvesterAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        # Simulate state: has inventory, at hub
        agent._state = agent._state  # reset
        # Give inventory and place at hub
        obs = _make_obs(
            node_type="TRADE_HUB",
            inventory={CommodityType.IRON: 5},
            resource_avail={},
        )
        # Force into SELL state
        from evomarket.agents.heuristic_agent import HarvesterState

        agent._state = HarvesterState.SELL
        result = agent.decide(obs)
        assert result.action.action_type == "post_order"


class TestTraderAgent:
    def test_returns_valid_action(self) -> None:
        agent = TraderAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_obs(node_type="TRADE_HUB")
        result = agent.decide(obs)
        assert result.action.action_type in {
            "idle",
            "move",
            "post_order",
            "accept_order",
            "harvest",
        }

    def test_sells_with_inventory(self) -> None:
        agent = TraderAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_obs(
            node_type="TRADE_HUB",
            inventory={CommodityType.IRON: 3},
            npc_prices={CommodityType.IRON: 4000},
        )
        result = agent.decide(obs)
        assert result.action.action_type == "post_order"


class TestSocialAgent:
    def test_returns_valid_action(self) -> None:
        agent = SocialAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_obs()
        result = agent.decide(obs)
        assert result.action is not None

    def test_accepts_trade_proposal(self) -> None:
        agent = SocialAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_obs(
            pending_proposals=[
                TradeProposalView(
                    trade_id="trade_001",
                    proposer_id="agent_002",
                    offer_commodities={},
                    offer_credits=5000,
                    request_commodities={CommodityType.IRON: 1},
                    request_credits=0,
                )
            ]
        )
        result = agent.decide(obs)
        assert result.action.action_type == "accept_trade"


class TestHoarderAgent:
    def test_harvests_at_resource(self) -> None:
        agent = HoarderAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_obs(node_type="RESOURCE")
        result = agent.decide(obs)
        assert result.action.action_type == "harvest"

    def test_panic_sells_low_credits(self) -> None:
        agent = HoarderAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_obs(
            credits=2000,
            inventory={CommodityType.IRON: 3},
        )
        result = agent.decide(obs)
        assert result.action.action_type == "post_order"


class TestExplorerAgent:
    def test_moves_frequently(self) -> None:
        agent = ExplorerAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_obs(node_type="TRADE_HUB", resource_avail={})
        moves = 0
        for _ in range(10):
            result = agent.decide(obs)
            if result.action.action_type == "move":
                moves += 1
        assert moves > 0

    def test_inspects_nearby_agents(self) -> None:
        agent = ExplorerAgent(seed=42)
        agent.on_spawn("agent_001", SimulationConfig())
        obs = _make_obs(
            node_type="TRADE_HUB",
            resource_avail={},
            agents_present=[
                AgentPublicView(agent_id="agent_002", display_name="Agent 2", age=5)
            ],
        )
        actions = set()
        for _ in range(20):
            result = agent.decide(obs)
            actions.add(result.action.action_type)
        assert "inspect" in actions or "move" in actions


class TestHeuristicAgentFactory:
    def test_creates_all_types(self) -> None:
        config = SimulationConfig()
        factory = HeuristicAgentFactory(config)
        types_seen = set()
        for i in range(config.population_size):
            agent = factory.create_agent(f"agent_{i:03d}")
            types_seen.add(type(agent).__name__)
        expected = {
            "HarvesterAgent",
            "TraderAgent",
            "SocialAgent",
            "HoarderAgent",
            "ExplorerAgent",
        }
        assert types_seen == expected

    def test_round_robin_distribution(self) -> None:
        config = SimulationConfig(
            population_size=6,
            agent_mix={"harvester": 3, "trader": 3},
        )
        factory = HeuristicAgentFactory(config)
        agents = [factory.create_agent(f"agent_{i:03d}") for i in range(6)]
        harvesters = sum(1 for a in agents if isinstance(a, HarvesterAgent))
        traders = sum(1 for a in agents if isinstance(a, TraderAgent))
        assert harvesters == 3
        assert traders == 3

    def test_respawn_wraps_around(self) -> None:
        config = SimulationConfig(
            population_size=2,
            agent_mix={"harvester": 1, "trader": 1},
        )
        factory = HeuristicAgentFactory(config)
        # Create initial + one respawn
        for i in range(3):
            agent = factory.create_agent(f"agent_{i:03d}")
            assert agent is not None
