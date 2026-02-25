"""Tests for the prompt renderer."""

from evomarket.agents.prompt_renderer import (
    render_prompt,
    _approx_tokens,
    _render_preamble,
)
from evomarket.core.types import CommodityType
from evomarket.engine.observation import (
    ActionAvailability,
    AgentObservation,
    AgentPublicView,
    AgentStateView,
    FillableOrder,
    MarketPriceView,
    MessageView,
    NodeView,
    OrderView,
    PreambleData,
    SellableItem,
    TradeProposalView,
)


def _default_availability(
    *,
    adjacent_nodes: list[str] | None = None,
    can_harvest: bool = False,
    harvestable_resources: dict[CommodityType, int] | None = None,
    can_sell_to_npc: bool = False,
    sellable_items: list[SellableItem] | None = None,
    can_buy_from_npc: bool = False,
    can_post_sell_order: bool = False,
    post_sell_inventory: dict[CommodityType, int] | None = None,
    can_post_buy_order: bool = True,
    fillable_orders: list[FillableOrder] | None = None,
    can_propose_trade: bool = False,
    tradeable_agents: list[str] | None = None,
    acceptable_trades: list[str] | None = None,
    can_inspect: bool = False,
) -> ActionAvailability:
    """Build a default ActionAvailability for tests."""
    adj = adjacent_nodes or ["node_trade_hub", "node_forest"]
    return ActionAvailability(
        can_move=bool(adj),
        adjacent_nodes=adj,
        can_harvest=can_harvest,
        harvestable_resources=harvestable_resources or {},
        can_sell_to_npc=can_sell_to_npc,
        sellable_items=sellable_items or [],
        can_buy_from_npc=can_buy_from_npc,
        can_post_sell_order=can_post_sell_order,
        post_sell_inventory=post_sell_inventory or {},
        can_post_buy_order=can_post_buy_order,
        fillable_orders=fillable_orders or [],
        can_propose_trade=can_propose_trade,
        tradeable_agents=tradeable_agents or [],
        acceptable_trades=acceptable_trades or [],
        can_inspect=can_inspect,
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
    action_availability: ActionAvailability | None = None,
) -> AgentObservation:
    """Build a test observation with sensible defaults."""
    if action_availability is None:
        action_availability = _default_availability(
            adjacent_nodes=adjacent_nodes or ["node_trade_hub", "node_forest"],
        )
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
            adjacent_node_info=[],
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
        action_availability=action_availability,
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
        avail = _default_availability(
            can_harvest=True,
            harvestable_resources={CommodityType.IRON: 5},
            can_sell_to_npc=True,
            sellable_items=[
                SellableItem(
                    commodity=CommodityType.IRON, quantity_held=2, npc_price=5000
                ),
            ],
            can_buy_from_npc=True,
            can_post_sell_order=True,
            post_sell_inventory={CommodityType.IRON: 2},
            can_post_buy_order=True,
            fillable_orders=[
                FillableOrder(
                    order_id="ord_001",
                    poster_id="agent_005",
                    side="sell",
                    commodity=CommodityType.IRON,
                    quantity=1,
                    price_per_unit=4500,
                ),
            ],
            can_propose_trade=True,
            tradeable_agents=["agent_005"],
            acceptable_trades=["trade_001"],
            can_inspect=True,
        )
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
            action_availability=avail,
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


class TestActionAvailabilityInPrompt:
    """Test that ActionAvailability controls which actions appear in the prompt."""

    def test_post_sell_order_hidden_without_inventory(self):
        """post_order sell should not appear when agent has no inventory."""
        avail = _default_availability(
            can_post_sell_order=False, can_post_buy_order=True
        )
        obs = _make_observation(action_availability=avail)
        prompt = render_prompt(obs, "", "agent_001")
        assert "post_order sell" not in prompt
        assert "post_order buy" in prompt

    def test_post_buy_order_hidden_without_credits(self):
        """post_order buy should not appear when agent has no credits."""
        avail = _default_availability(
            can_post_sell_order=True,
            post_sell_inventory={CommodityType.IRON: 3},
            can_post_buy_order=False,
        )
        obs = _make_observation(action_availability=avail)
        prompt = render_prompt(obs, "", "agent_001")
        assert "post_order sell" in prompt
        assert "post_order buy" not in prompt

    def test_post_order_both_hidden_at_order_limit(self):
        """Neither post_order variant should appear at order limit."""
        avail = _default_availability(
            can_post_sell_order=False, can_post_buy_order=False
        )
        obs = _make_observation(action_availability=avail)
        prompt = render_prompt(obs, "", "agent_001")
        assert "post_order" not in prompt

    def test_post_sell_order_shows_inventory(self):
        """post_order sell should show what the agent has."""
        avail = _default_availability(
            can_post_sell_order=True,
            post_sell_inventory={CommodityType.IRON: 3, CommodityType.WOOD: 2},
        )
        obs = _make_observation(action_availability=avail)
        prompt = render_prompt(obs, "", "agent_001")
        assert "post_order sell" in prompt
        assert "IRON=3" in prompt
        assert "WOOD=2" in prompt

    def test_post_buy_order_shows_credits(self):
        """post_order buy should show agent's credits."""
        avail = _default_availability(can_post_buy_order=True)
        obs = _make_observation(credits=15000, action_availability=avail)
        prompt = render_prompt(obs, "", "agent_001")
        assert "post_order buy" in prompt
        assert "credits=15.0" in prompt

    def test_propose_trade_hidden_at_limit(self):
        """propose_trade should not appear when can_propose_trade is False."""
        avail = _default_availability(
            can_propose_trade=False, tradeable_agents=["agent_005"]
        )
        obs = _make_observation(
            agents_present=[
                AgentPublicView(agent_id="agent_005", display_name="Agent 5", age=10),
            ],
            action_availability=avail,
        )
        prompt = render_prompt(obs, "", "agent_001")
        assert "propose_trade" not in prompt

    def test_propose_trade_shown_when_available(self):
        """propose_trade should appear when can_propose_trade is True."""
        avail = _default_availability(
            can_propose_trade=True, tradeable_agents=["agent_005"]
        )
        obs = _make_observation(
            agents_present=[
                AgentPublicView(agent_id="agent_005", display_name="Agent 5", age=10),
            ],
            action_availability=avail,
        )
        prompt = render_prompt(obs, "", "agent_001")
        assert "propose_trade" in prompt

    def test_harvest_hidden_at_non_resource_node(self):
        """harvest should not appear in valid actions when can_harvest is False."""
        avail = _default_availability(can_harvest=False)
        obs = _make_observation(node_type="TRADE_HUB", action_availability=avail)
        prompt = render_prompt(obs, "", "agent_001")
        # "harvest" may appear in strategic hints but not as a valid action
        assert "harvest  — gather resource" not in prompt

    def test_inspect_hidden_when_alone(self):
        """inspect should not appear when can_inspect is False."""
        avail = _default_availability(can_inspect=False)
        obs = _make_observation(action_availability=avail)
        prompt = render_prompt(obs, "", "agent_001")
        assert "inspect" not in prompt

    def test_accept_trade_only_shows_acceptable(self):
        """Only trades in acceptable_trades should appear as accept_trade actions."""
        avail = _default_availability(acceptable_trades=["trade_001"])
        obs = _make_observation(
            pending_proposals=[
                TradeProposalView(
                    trade_id="trade_001",
                    proposer_id="agent_005",
                    offer_commodities={CommodityType.IRON: 1},
                    offer_credits=0,
                    request_commodities={},
                    request_credits=1000,
                ),
                TradeProposalView(
                    trade_id="trade_002",
                    proposer_id="agent_006",
                    offer_commodities={CommodityType.WOOD: 1},
                    offer_credits=0,
                    request_commodities={CommodityType.IRON: 10},
                    request_credits=0,
                ),
            ],
            action_availability=avail,
        )
        prompt = render_prompt(obs, "", "agent_001")
        assert "accept_trade trade_001" in prompt
        assert "accept_trade trade_002" not in prompt


class TestMarketPricesInPrompt:
    """Test that market prices are rendered in the prompt."""

    def test_renders_market_prices_section(self):
        market_prices = [
            MarketPriceView(
                node_id="node_hub_iron",
                node_name="Hub Iron",
                prices={CommodityType.IRON: 2000, CommodityType.WOOD: 5000},
            ),
            MarketPriceView(
                node_id="node_hub_herbs",
                node_name="Hub Herbs",
                prices={CommodityType.HERBS: 4500, CommodityType.IRON: 5000},
            ),
        ]
        obs = _make_observation()
        # Replace with an observation that has market_prices
        obs = AgentObservation(
            preamble=obs.preamble,
            prompt_document=obs.prompt_document,
            agent_state=obs.agent_state,
            node_info=obs.node_info,
            agents_present=obs.agents_present,
            posted_orders=obs.posted_orders,
            messages_received=obs.messages_received,
            pending_proposals=obs.pending_proposals,
            own_orders=obs.own_orders,
            own_pending_proposals=obs.own_pending_proposals,
            own_will=obs.own_will,
            action_availability=obs.action_availability,
            market_prices=market_prices,
        )
        prompt = render_prompt(obs, "", "agent_001")
        assert "MARKET PRICES" in prompt
        assert "node_hub_iron" in prompt
        assert "node_hub_herbs" in prompt
        assert "Hub Iron" in prompt
        assert "Hub Herbs" in prompt
        # Check price values rendered as credits
        assert "2.0cr" in prompt
        assert "5.0cr" in prompt
        assert "4.5cr" in prompt

    def test_marks_current_location(self):
        market_prices = [
            MarketPriceView(
                node_id="node_iron_peak",
                node_name="Iron Peak",
                prices={CommodityType.IRON: 5000},
            ),
            MarketPriceView(
                node_id="node_hub_herbs",
                node_name="Hub Herbs",
                prices={CommodityType.HERBS: 4500},
            ),
        ]
        obs = _make_observation()
        obs = AgentObservation(
            preamble=obs.preamble,
            prompt_document=obs.prompt_document,
            agent_state=obs.agent_state,
            node_info=obs.node_info,
            agents_present=obs.agents_present,
            posted_orders=obs.posted_orders,
            messages_received=obs.messages_received,
            pending_proposals=obs.pending_proposals,
            own_orders=obs.own_orders,
            own_pending_proposals=obs.own_pending_proposals,
            own_will=obs.own_will,
            action_availability=obs.action_availability,
            market_prices=market_prices,
        )
        prompt = render_prompt(obs, "", "agent_001")
        # Agent is at node_iron_peak, so the market prices line should have the marker
        assert "YOU ARE HERE" in prompt
        # Find the line within the MARKET PRICES section
        in_market_section = False
        found = False
        for line in prompt.split("\n"):
            if "MARKET PRICES" in line:
                in_market_section = True
                continue
            if in_market_section and "node_iron_peak" in line:
                assert "YOU ARE HERE" in line
                found = True
                break
        assert found, "Did not find node_iron_peak in MARKET PRICES section"

    def test_no_market_prices_section_when_none(self):
        obs = _make_observation()
        prompt = render_prompt(obs, "", "agent_001")
        assert "MARKET PRICES" not in prompt
