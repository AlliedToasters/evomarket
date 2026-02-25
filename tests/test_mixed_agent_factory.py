"""Tests for MixedAgentFactory."""

from __future__ import annotations

import pytest

from evomarket.agents.heuristic_agent import (
    ExplorerAgent,
    HarvesterAgent,
    TraderAgent,
)
from evomarket.agents.llm_agent import LLMAgent, MixedAgentFactory
from evomarket.agents.llm_backend import LLMBackend
from evomarket.agents.random_agent import RandomAgent
from evomarket.simulation.config import SimulationConfig


def _make_backend(model: str = "test-model") -> LLMBackend:
    return LLMBackend(model=model, base_url="http://localhost:11434/v1")


class TestMixedAgentFactory:
    def test_heuristic_only(self) -> None:
        config = SimulationConfig(
            population_size=4,
            agent_mix={"harvester": 2, "trader": 2},
        )
        factory = MixedAgentFactory(config)
        agents = [factory.create_agent(f"a{i}") for i in range(4)]
        assert isinstance(agents[0], HarvesterAgent)
        assert isinstance(agents[1], HarvesterAgent)
        assert isinstance(agents[2], TraderAgent)
        assert isinstance(agents[3], TraderAgent)

    def test_mixed_heuristic_and_llm(self) -> None:
        config = SimulationConfig(
            population_size=4,
            agent_mix={"harvester": 2, "llm:haiku": 2},
            llm_backends={"haiku": {"model": "anthropic/claude-3.5-haiku"}},
        )
        backend = _make_backend("anthropic/claude-3.5-haiku")
        factory = MixedAgentFactory(config, llm_backends={"haiku": backend})
        agents = [factory.create_agent(f"a{i}") for i in range(4)]
        assert isinstance(agents[0], HarvesterAgent)
        assert isinstance(agents[1], HarvesterAgent)
        assert isinstance(agents[2], LLMAgent)
        assert isinstance(agents[3], LLMAgent)

    def test_bare_llm_key(self) -> None:
        config = SimulationConfig(
            population_size=2,
            agent_mix={"llm": 2},
        )
        backend = _make_backend()
        factory = MixedAgentFactory(config, llm_backends={"": backend})
        agents = [factory.create_agent(f"a{i}") for i in range(2)]
        assert all(isinstance(a, LLMAgent) for a in agents)

    def test_random_agent_type(self) -> None:
        config = SimulationConfig(
            population_size=3,
            agent_mix={"random": 1, "harvester": 2},
        )
        factory = MixedAgentFactory(config)
        agents = [factory.create_agent(f"a{i}") for i in range(3)]
        assert isinstance(agents[0], RandomAgent)
        assert isinstance(agents[1], HarvesterAgent)

    def test_multiple_llm_backends(self) -> None:
        config = SimulationConfig(
            population_size=4,
            agent_mix={"llm:haiku": 2, "llm:grok": 2},
            llm_backends={
                "haiku": {"model": "anthropic/claude-3.5-haiku"},
                "grok": {"model": "x-ai/grok-3-mini-beta"},
            },
        )
        haiku_backend = _make_backend("anthropic/claude-3.5-haiku")
        grok_backend = _make_backend("x-ai/grok-3-mini-beta")
        factory = MixedAgentFactory(
            config,
            llm_backends={"haiku": haiku_backend, "grok": grok_backend},
        )
        agents = [factory.create_agent(f"a{i}") for i in range(4)]
        assert all(isinstance(a, LLMAgent) for a in agents)

    def test_missing_llm_backend_raises(self) -> None:
        config = SimulationConfig(
            population_size=2,
            agent_mix={"llm:haiku": 2},
            llm_backends={"haiku": {"model": "test"}},
        )
        factory = MixedAgentFactory(config, llm_backends={})
        with pytest.raises(ValueError, match="No LLM backend"):
            factory.create_agent("a0")

    def test_round_robin_wraps(self) -> None:
        config = SimulationConfig(
            population_size=2,
            agent_mix={"harvester": 1, "explorer": 1},
        )
        factory = MixedAgentFactory(config)
        agents = [factory.create_agent(f"a{i}") for i in range(4)]
        assert isinstance(agents[0], HarvesterAgent)
        assert isinstance(agents[1], ExplorerAgent)
        # Wraps around
        assert isinstance(agents[2], HarvesterAgent)
        assert isinstance(agents[3], ExplorerAgent)
