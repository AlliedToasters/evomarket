"""Abstract agent interface and factory protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evomarket.engine.actions import AgentTurnResult
    from evomarket.engine.observation import AgentObservation
    from evomarket.simulation.config import SimulationConfig


class BaseAgent(ABC):
    """Abstract base class for all agent implementations."""

    @abstractmethod
    def decide(self, observation: AgentObservation) -> AgentTurnResult:
        """Given an observation, return an action and optional scratchpad edit."""
        ...

    @abstractmethod
    def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
        """Called once when the agent is created, before any decide() calls."""
        ...

    def get_state(self) -> dict | None:
        """Serialize agent-internal state for checkpointing. Returns None if not supported."""
        return None

    def set_state(self, state: dict) -> None:
        """Restore agent-internal state from a checkpoint. No-op by default."""


class AgentFactory(ABC):
    """Abstract factory for creating agent instances."""

    @abstractmethod
    def create_agent(self, agent_id: str) -> BaseAgent:
        """Create a new agent instance for the given agent ID."""
        ...
