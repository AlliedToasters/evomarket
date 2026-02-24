"""Tests for the prompt renderer."""

from evomarket.agents.prompt_renderer import (
    render_prompt,
    _approx_tokens,
    _render_preamble,
)
from evomarket.core.types import CommodityType
from evomarket.engine.observation import (
    AgentObservation,
    AgentPublicView,
    AgentStateView,
    MessageView,
    NodeView,
    OrderView,
    PreambleData,
    TradeProposalView,
)


def _make_observation(
    *,
    tick: int = 10,
    credits: int = 15000,
    inventory: dict[CommodityType, int] | None = None,
    node_type: str = "RESOURCE",
    npc_prices: dict[CommodityType, int] | None = None,
    resource_availability: dict[CommodityType, int] | None = None,
    adjacent_nodes: list[str] | None = None,
    agents_present: list[AgentPublicView] | None = None,
    posted_orders: list[OrderView] | None = None,
    messages_received: list[MessageView] | None = None,
    pending_proposals: list[TradeProposalView] | None = None,
) -> AgentObservation:
    """Build a test observation with sensible defaults."""
    return AgentObservation(
        preamble=PreambleData(tick=tick),
        prompt_document="",
        agent_state=AgentStateView(
            location="node_iron_peak",
            credits=credits,
            inventory=inventory or {},
            age=5,
            grace_ticks_remaining=0,
        ),
        node_info=NodeView(
            node_id="node_iron_peak",
            name="Iron Peak",
            node_type=node_type,
            adjacent_nodes=adjacent_nodes or ["node_trade_hub", "node_forest"],
            npc_prices=npc_prices or {},
            resource_availability=resource_availability or {},
        ),
        agents_present=agents_present or [],
        posted_orders=posted_orders or [],
        messages_received=messages_received or [],
        pending_proposals=pending_proposals or [],
        own_orders=[],
        own_pending_proposals=[],
        own_will={},
    )


class TestRenderPromptSections:
    """Test that the prompt contains all three sections."""

    def test_contains_preamble(self):
        obs = _make_observation()
        prompt = render_prompt(obs, "", "agent_001")
        assert "=== EVOMARKET AGENT ===" in prompt

    def test_contains_scratchpad_section(self):
        obs = _make_observation()
        prompt = render_prompt(obs, "", "agent_001")
        assert "=== SCRATCHPAD ===" in prompt

    def test_contains_world_state(self):
        obs = _make_observation()
        prompt = render_prompt(obs, "", "agent_001")
        assert "=== WORLD STATE ===" in prompt

    def test_sections_in_order(self):
        obs = _make_observation()
        prompt = render_prompt(obs, "", "agent_001")
        preamble_pos = prompt.index("=== EVOMARKET AGENT ===")
        scratchpad_pos = prompt.index("=== SCRATCHPAD ===")
        world_pos = prompt.index("=== WORLD STATE ===")
        assert preamble_pos < scratchpad_pos < world_pos


class TestPreamble:
    """Test preamble content and token efficiency."""

    def test_includes_agent_id(self):
        obs = _make_observation()
        prompt = render_prompt(obs, "", "agent_042")
        assert "agent_042" in prompt

    def test_includes_action_reference(self):
        """With a rich observation, all action types should appear."""
        obs = _make_observation(
            node_type="RESOURCE",
            resource_availability={CommodityType.IRON: 5},
            npc_prices={CommodityType.IRON: 5000},
            inventory={CommodityType.IRON: 2},
            agents_present=[
                AgentPublicView(agent_id="agent_005", display_name="Agent 5", age=10),
            ],
            posted_orders=[
                OrderView(
                    order_id="ord_001",
                    poster_id="agent_005",
                    side="sell",
                    commodity=CommodityType.IRON,
                    quantity=1,
                    price_per_unit=4500,
                ),
            ],
            pending_proposals=[
                TradeProposalView(
                    trade_id="trade_001",
                    proposer_id="agent_005",
                    offer_commodities={CommodityType.IRON: 1},
                    offer_credits=0,
                    request_commodities={},
                    request_credits=1000,
                ),
            ],
        )
        prompt = render_prompt(obs, "", "agent_001")
        for action in [
            "move",
            "harvest",
            "post_order",
            "accept_order",
            "idle",
            "propose_trade",
            "accept_trade",
            "send_message",
            "inspect",
        ]:
            assert action in prompt, f"Expected '{action}' in prompt"

    def test_includes_response_format(self):
        obs = _make_observation()
        prompt = render_prompt(obs, "", "agent_001")
        assert "ACTION:" in prompt
        assert "SCRATCHPAD:" in prompt
        assert "REASONING:" in prompt

    def test_preamble_contains_valid_actions_header(self):
        obs = _make_observation()
        preamble = _render_preamble("agent_001", "", obs)
        assert "VALID ACTIONS THIS TICK" in preamble

    def test_preamble_token_efficiency(self):
        """Preamble should be under 600 tokens (dynamic actions may be longer)."""
        obs = _make_observation()
        preamble = _render_preamble("agent_001", "", obs)
        tokens = _approx_tokens(preamble)
        assert tokens < 600, f"Preamble is {tokens} tokens, should be under 600"


class TestScratchpadSection:
    """Test scratchpad rendering."""

    def test_empty_scratchpad(self):
        obs = _make_observation()
        prompt = render_prompt(obs, "", "agent_001")
        assert "(empty)" in prompt

    def test_nonempty_scratchpad(self):
        obs = _make_observation()
        scratchpad = "Strategy: harvest iron then sell at hub"
        prompt = render_prompt(obs, scratchpad, "agent_001")
        assert scratchpad in prompt


class TestWorldState:
    """Test world state rendering."""

    def test_renders_credits(self):
        obs = _make_observation(credits=15000)
        prompt = render_prompt(obs, "", "agent_001")
        assert "15.0" in prompt

    def test_renders_inventory(self):
        obs = _make_observation(inventory={CommodityType.IRON: 3})
        prompt = render_prompt(obs, "", "agent_001")
        assert "IRON=3" in prompt

    def test_renders_node_info(self):
        obs = _make_observation()
        prompt = render_prompt(obs, "", "agent_001")
        assert "node_iron_peak" in prompt
        assert "Iron Peak" in prompt
        assert "RESOURCE" in prompt

    def test_renders_adjacent_nodes(self):
        obs = _make_observation(adjacent_nodes=["node_trade_hub", "node_forest"])
        prompt = render_prompt(obs, "", "agent_001")
        assert "node_trade_hub" in prompt
        assert "node_forest" in prompt

    def test_renders_npc_prices(self):
        obs = _make_observation(npc_prices={CommodityType.IRON: 5000})
        prompt = render_prompt(obs, "", "agent_001")
        assert "IRON" in prompt
        assert "5.0" in prompt

    def test_renders_resource_availability(self):
        obs = _make_observation(resource_availability={CommodityType.IRON: 8})
        prompt = render_prompt(obs, "", "agent_001")
        assert "IRON=8" in prompt

    def test_renders_nearby_agents(self):
        obs = _make_observation(
            agents_present=[
                AgentPublicView(agent_id="agent_005", display_name="Agent 5", age=10),
            ]
        )
        prompt = render_prompt(obs, "", "agent_001")
        assert "agent_005" in prompt

    def test_renders_posted_orders(self):
        obs = _make_observation(
            posted_orders=[
                OrderView(
                    order_id="ord_001",
                    poster_id="agent_003",
                    side="sell",
                    commodity=CommodityType.IRON,
                    quantity=2,
                    price_per_unit=4500,
                ),
            ]
        )
        prompt = render_prompt(obs, "", "agent_001")
        assert "ord_001" in prompt
        assert "sell" in prompt

    def test_renders_messages(self):
        obs = _make_observation(
            messages_received=[
                MessageView(
                    message_id="msg_001",
                    sender_id="agent_003",
                    text="prices are high",
                    sent_tick=8,
                ),
            ]
        )
        prompt = render_prompt(obs, "", "agent_001")
        assert "agent_003" in prompt
        assert "prices are high" in prompt

    def test_renders_trade_proposals(self):
        obs = _make_observation(
            pending_proposals=[
                TradeProposalView(
                    trade_id="trade_001",
                    proposer_id="agent_007",
                    offer_commodities={CommodityType.IRON: 2},
                    offer_credits=0,
                    request_commodities={},
                    request_credits=5000,
                ),
            ]
        )
        prompt = render_prompt(obs, "", "agent_001")
        assert "trade_001" in prompt
        assert "agent_007" in prompt
