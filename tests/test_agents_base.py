"""Tests for BaseAgent and AgentFactory ABCs."""

import pytest

from evomarket.agents.base import AgentFactory, BaseAgent
from evomarket.engine.actions import AgentTurnResult, IdleAction
from evomarket.engine.observation import AgentObservation
from evomarket.simulation.config import SimulationConfig


class TestBaseAgentABC:
    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore[abstract]

    def test_missing_decide_raises(self) -> None:
        class BadAgent(BaseAgent):
            def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
                pass

        with pytest.raises(TypeError):
            BadAgent()  # type: ignore[abstract]

    def test_missing_on_spawn_raises(self) -> None:
        class BadAgent(BaseAgent):
            def decide(self, observation: AgentObservation) -> AgentTurnResult:
                return AgentTurnResult(action=IdleAction())

        with pytest.raises(TypeError):
            BadAgent()  # type: ignore[abstract]

    def test_valid_subclass(self) -> None:
        class GoodAgent(BaseAgent):
            def decide(self, observation: AgentObservation) -> AgentTurnResult:
                return AgentTurnResult(action=IdleAction())

            def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
                self.agent_id = agent_id

        agent = GoodAgent()
        assert isinstance(agent, BaseAgent)


class TestAgentFactoryABC:
    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            AgentFactory()  # type: ignore[abstract]

    def test_valid_subclass(self) -> None:
        class GoodFactory(AgentFactory):
            def create_agent(self, agent_id: str) -> BaseAgent:
                class DummyAgent(BaseAgent):
                    def decide(self, observation: AgentObservation) -> AgentTurnResult:
                        return AgentTurnResult(action=IdleAction())

                    def on_spawn(self, aid: str, config: SimulationConfig) -> None:
                        pass

                agent = DummyAgent()
                return agent

        factory = GoodFactory()
        agent = factory.create_agent("agent_001")
        assert isinstance(agent, BaseAgent)
