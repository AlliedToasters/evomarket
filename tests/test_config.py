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
