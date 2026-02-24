"""Tests for the action parser."""

import logging

from evomarket.agents.action_parser import parse_response
from evomarket.core.types import CommodityType
from evomarket.engine.actions import (
    AcceptOrderAction,
    AcceptTradeAction,
    HarvestAction,
    IdleAction,
    InspectAction,
    MoveAction,
    PostOrderAction,
    ProposeTradeAction,
    SendMessageAction,
    UpdateWillAction,
)


# ---------------------------------------------------------------------------
# Structured parsing — well-formed actions
# ---------------------------------------------------------------------------


class TestStructuredParsing:
    """Test parsing of well-formed ACTION: lines."""

    def test_idle(self):
        action, _ = parse_response("ACTION: idle")
        assert isinstance(action, IdleAction)

    def test_harvest(self):
        action, _ = parse_response("ACTION: harvest")
        assert isinstance(action, HarvestAction)

    def test_move(self):
        action, _ = parse_response("ACTION: move node_iron_peak")
        assert isinstance(action, MoveAction)
        assert action.target_node == "node_iron_peak"

    def test_post_order_sell(self):
        action, _ = parse_response("ACTION: post_order sell IRON 3 4500")
        assert isinstance(action, PostOrderAction)
        assert action.side == "sell"
        assert action.commodity == CommodityType.IRON
        assert action.quantity == 3
        assert action.price == 4500

    def test_post_order_buy(self):
        action, _ = parse_response("ACTION: post_order buy WOOD 1 3000")
        assert isinstance(action, PostOrderAction)
        assert action.side == "buy"
        assert action.commodity == CommodityType.WOOD
        assert action.quantity == 1
        assert action.price == 3000

    def test_accept_order(self):
        action, _ = parse_response("ACTION: accept_order ord_abc123")
        assert isinstance(action, AcceptOrderAction)
        assert action.order_id == "ord_abc123"

    def test_propose_trade(self):
        action, _ = parse_response(
            "ACTION: propose_trade agent_005 offer:iron=2 request:credits=5000"
        )
        assert isinstance(action, ProposeTradeAction)
        assert action.target_agent == "agent_005"
        assert action.offer == {"IRON": 2}
        assert action.request == {"credits": 5000}

    def test_accept_trade(self):
        action, _ = parse_response("ACTION: accept_trade trade_001")
        assert isinstance(action, AcceptTradeAction)
        assert action.trade_id == "trade_001"

    def test_send_message(self):
        action, _ = parse_response("ACTION: send_message agent_005 hello there")
        assert isinstance(action, SendMessageAction)
        assert action.target == "agent_005"
        assert action.text == "hello there"

    def test_send_message_broadcast(self):
        action, _ = parse_response("ACTION: send_message broadcast prices are high")
        assert isinstance(action, SendMessageAction)
        assert action.target == "broadcast"
        assert action.text == "prices are high"

    def test_inspect(self):
        action, _ = parse_response("ACTION: inspect agent_003")
        assert isinstance(action, InspectAction)
        assert action.target_agent == "agent_003"

    def test_update_will(self):
        action, _ = parse_response("ACTION: update_will agent_001=0.5 agent_002=0.5")
        assert isinstance(action, UpdateWillAction)
        assert action.distribution == {"agent_001": 0.5, "agent_002": 0.5}


# ---------------------------------------------------------------------------
# SCRATCHPAD extraction
# ---------------------------------------------------------------------------


class TestScratchpadExtraction:
    """Test SCRATCHPAD section extraction."""

    def test_scratchpad_single_line(self):
        _, scratchpad = parse_response(
            "ACTION: harvest\nSCRATCHPAD: remember to sell\nREASONING: need resources"
        )
        assert scratchpad == "remember to sell"

    def test_scratchpad_multi_line(self):
        _, scratchpad = parse_response(
            "ACTION: harvest\nSCRATCHPAD: line one\nline two\nREASONING: because"
        )
        assert scratchpad == "line one\nline two"

    def test_no_scratchpad(self):
        _, scratchpad = parse_response("ACTION: idle")
        assert scratchpad is None

    def test_empty_scratchpad(self):
        _, scratchpad = parse_response("ACTION: idle\nSCRATCHPAD: \nREASONING: nothing")
        assert scratchpad is None  # empty string becomes None

    def test_scratchpad_at_end(self):
        _, scratchpad = parse_response("ACTION: harvest\nSCRATCHPAD: final notes here")
        assert scratchpad == "final notes here"


# ---------------------------------------------------------------------------
# Regex fallback
# ---------------------------------------------------------------------------


class TestRegexFallback:
    """Test regex-based action extraction from freeform text."""

    def test_harvest_keyword(self):
        action, _ = parse_response("I think I should harvest resources now")
        assert isinstance(action, HarvestAction)

    def test_idle_keyword(self):
        action, _ = parse_response("I'll just idle this turn")
        assert isinstance(action, IdleAction)

    def test_move_keyword(self):
        action, _ = parse_response("Let me move to node_iron_peak for resources")
        assert isinstance(action, MoveAction)
        assert action.target_node == "node_iron_peak"

    def test_inspect_keyword(self):
        action, _ = parse_response("I want to inspect agent_003 to see their inventory")
        assert isinstance(action, InspectAction)
        assert action.target_agent == "agent_003"

    def test_accept_order_keyword(self):
        action, _ = parse_response("I should accept_order ord_xyz")
        assert isinstance(action, AcceptOrderAction)
        assert action.order_id == "ord_xyz"

    def test_accept_trade_keyword(self):
        action, _ = parse_response("I'll accept trade trade_abc")
        assert isinstance(action, AcceptTradeAction)
        assert action.trade_id == "trade_abc"


# ---------------------------------------------------------------------------
# IdleAction fallback
# ---------------------------------------------------------------------------


class TestIdleFallback:
    """Test that unparseable responses become IdleAction."""

    def test_complete_gibberish(self):
        action, _ = parse_response("asdfghjkl 12345")
        assert isinstance(action, IdleAction)

    def test_empty_response(self):
        action, _ = parse_response("")
        assert isinstance(action, IdleAction)

    def test_whitespace_only(self):
        action, _ = parse_response("   \n  \n  ")
        assert isinstance(action, IdleAction)


# ---------------------------------------------------------------------------
# Parse failure logging
# ---------------------------------------------------------------------------


class TestParseFailureLogging:
    """Test that parse failures are logged."""

    def test_gibberish_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="evomarket.agents.action_parser"):
            parse_response("completely unparseable gibberish xyz")
        assert any("could not parse action" in r.message for r in caplog.records)

    def test_empty_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="evomarket.agents.action_parser"):
            parse_response("")
        assert any("empty LLM response" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Generous tolerance
# ---------------------------------------------------------------------------


class TestGenerousTolerance:
    """Test input tolerance for whitespace, casing, and commodity names."""

    def test_extra_whitespace(self):
        action, _ = parse_response("ACTION:   move   node_iron_peak  ")
        assert isinstance(action, MoveAction)
        assert action.target_node == "node_iron_peak"

    def test_uppercase_action(self):
        action, _ = parse_response("ACTION: MOVE node_iron_peak")
        assert isinstance(action, MoveAction)

    def test_mixed_case_action(self):
        action, _ = parse_response("ACTION: Harvest")
        assert isinstance(action, HarvestAction)

    def test_commodity_lowercase(self):
        action, _ = parse_response("ACTION: post_order sell iron 2 3000")
        assert isinstance(action, PostOrderAction)
        assert action.commodity == CommodityType.IRON

    def test_commodity_mixed_case(self):
        action, _ = parse_response("ACTION: post_order sell Iron 2 3000")
        assert isinstance(action, PostOrderAction)
        assert action.commodity == CommodityType.IRON

    def test_commodity_uppercase(self):
        action, _ = parse_response("ACTION: post_order sell IRON 2 3000")
        assert isinstance(action, PostOrderAction)
        assert action.commodity == CommodityType.IRON

    def test_all_commodities_recognized(self):
        for commodity in CommodityType:
            action, _ = parse_response(
                f"ACTION: post_order sell {commodity.value.lower()} 1 1000"
            )
            assert isinstance(action, PostOrderAction)
            assert action.commodity == commodity


# ---------------------------------------------------------------------------
# Full response with all sections
# ---------------------------------------------------------------------------


class TestFullResponse:
    """Test complete multi-section responses."""

    def test_full_response_with_all_sections(self):
        response = (
            "ACTION: move node_trade_hub\n"
            "SCRATCHPAD: heading to hub to sell iron\n"
            "REASONING: iron prices are high at the hub right now"
        )
        action, scratchpad = parse_response(response)
        assert isinstance(action, MoveAction)
        assert action.target_node == "node_trade_hub"
        assert scratchpad == "heading to hub to sell iron"

    def test_action_only_no_extras(self):
        action, scratchpad = parse_response("ACTION: harvest")
        assert isinstance(action, HarvestAction)
        assert scratchpad is None
