"""Tests for Agent model."""

import pytest

from evomarket.core.agent import Agent
from evomarket.core.types import CommodityType


def _make_agent(**overrides) -> Agent:  # type: ignore[no-untyped-def]
    defaults = {
        "agent_id": "agent_000",
        "display_name": "Test Agent",
        "location": "node_spawn",
        "credits": 30_000,
        "inventory": {CommodityType.IRON: 0, CommodityType.WOOD: 0},
        "age": 0,
        "alive": True,
        "will": {},
        "prompt_document": "",
        "grace_ticks_remaining": 5,
    }
    defaults.update(overrides)
    return Agent(**defaults)


class TestAgentConstruction:
    def test_valid_agent(self) -> None:
        agent = _make_agent()
        assert agent.agent_id == "agent_000"
        assert agent.credits == 30_000
        assert agent.alive is True

    def test_json_round_trip(self) -> None:
        agent = _make_agent(will={"agent_001": 0.5})
        json_str = agent.model_dump_json()
        restored = Agent.model_validate_json(json_str)
        assert restored == agent

    def test_agent_id_format(self) -> None:
        for i in range(3):
            agent = _make_agent(agent_id=f"agent_{i:03d}")
            assert agent.agent_id == f"agent_{i:03d}"


class TestWillValidation:
    def test_valid_will(self) -> None:
        agent = _make_agent(will={"agent_001": 0.5, "agent_002": 0.3})
        assert sum(agent.will.values()) == pytest.approx(0.8)

    def test_will_exceeds_100_percent(self) -> None:
        with pytest.raises(ValueError, match="must be ≤ 1.0"):
            _make_agent(will={"agent_001": 0.6, "agent_002": 0.6})

    def test_negative_will_percentage(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            _make_agent(will={"agent_001": -0.1})

    def test_empty_will(self) -> None:
        agent = _make_agent(will={})
        assert agent.will == {}

    def test_will_exactly_100_percent(self) -> None:
        agent = _make_agent(will={"agent_001": 0.5, "agent_002": 0.5})
        assert sum(agent.will.values()) == pytest.approx(1.0)


class TestInventoryValidation:
    def test_valid_inventory(self) -> None:
        agent = _make_agent(inventory={CommodityType.IRON: 5, CommodityType.WOOD: 0})
        assert agent.inventory[CommodityType.IRON] == 5

    def test_negative_inventory_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            _make_agent(inventory={CommodityType.IRON: -1})


class TestCredits:
    def test_positive_credits(self) -> None:
        agent = _make_agent(credits=30_000)
        assert agent.credits == 30_000

    def test_zero_credits(self) -> None:
        agent = _make_agent(credits=0)
        assert agent.credits == 0

    def test_credits_can_go_negative_via_mutation(self) -> None:
        """Engine may set credits negative to signal death."""
        agent = _make_agent(credits=100)
        agent.credits = -500
        assert agent.credits == -500
