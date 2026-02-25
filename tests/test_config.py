"""Tests for SimulationConfig."""

import json

import pytest

from evomarket.core.types import MILLICREDITS_PER_CREDIT
from evomarket.simulation.config import SimulationConfig


class TestSimulationConfigDefaults:
    def test_default_construction(self) -> None:
        config = SimulationConfig()
        assert config.seed == 42
        assert config.population_size == 20
        assert config.ticks_per_episode == 500
        assert sum(config.agent_mix.values()) == config.population_size

    def test_default_agent_mix_types(self) -> None:
        config = SimulationConfig()
        assert "harvester" in config.agent_mix
        assert "trader" in config.agent_mix
        assert "social" in config.agent_mix
        assert "hoarder" in config.agent_mix
        assert "explorer" in config.agent_mix


class TestCreditConversion:
    def test_survival_tax_conversion(self) -> None:
        config = SimulationConfig()
        wc = config.to_world_config()
        assert wc.survival_tax == round(config.survival_tax * MILLICREDITS_PER_CREDIT)

    def test_starting_credits_conversion(self) -> None:
        config = SimulationConfig()
        wc = config.to_world_config()
        assert wc.starting_credits == round(
            config.starting_credits * MILLICREDITS_PER_CREDIT
        )

    def test_fractional_credits(self) -> None:
        config = SimulationConfig(starting_credits=30.5)
        wc = config.to_world_config()
        assert wc.starting_credits == 30_500

    def test_total_supply_conversion(self) -> None:
        config = SimulationConfig()
        wc = config.to_world_config()
        assert wc.total_credit_supply == 10_000 * MILLICREDITS_PER_CREDIT

    def test_world_config_valid(self) -> None:
        config = SimulationConfig()
        wc = config.to_world_config()
        # Should not raise
        assert wc.num_nodes == config.num_nodes
        assert wc.population_size == config.population_size


class TestJsonSerialization:
    def test_round_trip(self) -> None:
        original = SimulationConfig()
        data = original.to_json()
        restored = SimulationConfig.from_json(data)
        assert original == restored

    def test_round_trip_string(self) -> None:
        original = SimulationConfig()
        s = original.to_json_string()
        restored = SimulationConfig.from_json_string(s)
        assert original == restored

    def test_custom_config_round_trip(self) -> None:
        original = SimulationConfig(
            seed=123,
            population_size=10,
            agent_mix={"harvester": 5, "trader": 5},
            ticks_per_episode=100,
        )
        data = original.to_json()
        restored = SimulationConfig.from_json(data)
        assert original == restored

    def test_json_is_valid_json(self) -> None:
        config = SimulationConfig()
        s = config.to_json_string()
        parsed = json.loads(s)
        assert isinstance(parsed, dict)
        assert parsed["seed"] == 42


class TestValidation:
    def test_agent_mix_mismatch(self) -> None:
        with pytest.raises(ValueError, match="agent_mix sum"):
            SimulationConfig(population_size=20, agent_mix={"harvester": 5})

    def test_unknown_agent_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown agent type"):
            SimulationConfig(population_size=5, agent_mix={"unknown_type": 5})

    def test_insufficient_credit_supply(self) -> None:
        with pytest.raises(ValueError, match="insufficient"):
            SimulationConfig(
                total_credit_supply=10.0,
                starting_credits=30.0,
                population_size=20,
                agent_mix={"harvester": 20},
            )

    def test_invalid_ticks(self) -> None:
        with pytest.raises(ValueError, match="ticks_per_episode"):
            SimulationConfig(
                population_size=1,
                agent_mix={"harvester": 1},
                ticks_per_episode=0,
            )

    def test_custom_agent_mix(self) -> None:
        config = SimulationConfig(
            population_size=10,
            agent_mix={"harvester": 10},
        )
        assert config.agent_mix == {"harvester": 10}

    def test_llm_colon_valid_with_backend(self) -> None:
        config = SimulationConfig(
            population_size=4,
            agent_mix={"harvester": 2, "llm:haiku": 2},
            llm_backends={"haiku": {"model": "anthropic/claude-3.5-haiku"}},
        )
        assert "llm:haiku" in config.agent_mix

    def test_llm_colon_missing_backend_raises(self) -> None:
        with pytest.raises(ValueError, match="llm:grok"):
            SimulationConfig(
                population_size=4,
                agent_mix={"harvester": 2, "llm:grok": 2},
                llm_backends={},
            )

    def test_bare_llm_still_valid(self) -> None:
        config = SimulationConfig(
            population_size=4,
            agent_mix={"llm": 4},
        )
        assert config.agent_mix == {"llm": 4}

    def test_multiple_llm_backends(self) -> None:
        config = SimulationConfig(
            population_size=8,
            agent_mix={"llm:haiku": 4, "llm:grok": 4},
            llm_backends={
                "haiku": {"model": "anthropic/claude-3.5-haiku"},
                "grok": {"model": "x-ai/grok-3-mini-beta"},
            },
        )
        assert sum(config.agent_mix.values()) == 8

    def test_llm_backends_serialization_round_trip(self) -> None:
        original = SimulationConfig(
            population_size=4,
            agent_mix={"harvester": 2, "llm:haiku": 2},
            llm_backends={"haiku": {"model": "anthropic/claude-3.5-haiku"}},
        )
        data = original.to_json()
        restored = SimulationConfig.from_json(data)
        assert restored.llm_backends == original.llm_backends
        assert restored.agent_mix == original.agent_mix
