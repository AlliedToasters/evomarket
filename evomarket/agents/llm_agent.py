"""LLM-backed agent — uses a language model to decide actions each tick."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp

from evomarket.agents.action_parser import parse_response
from evomarket.agents.base import AgentFactory, BaseAgent
from evomarket.agents.llm_backend import LLMBackend
from evomarket.agents.prompt_renderer import render_prompt
from evomarket.engine.actions import AgentTurnResult, IdleAction

if TYPE_CHECKING:
    from evomarket.engine.observation import AgentObservation
    from evomarket.simulation.config import SimulationConfig

logger = logging.getLogger(__name__)


class LLMAgent(BaseAgent):
    """Agent that uses an LLM to decide actions each tick.

    Orchestrates: render_prompt → backend.generate → parse_response
    """

    def __init__(self, backend: LLMBackend) -> None:
        self._backend = backend
        self._agent_id: str = ""
        self._scratchpad: str = ""

    def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
        """Store agent ID for prompt rendering."""
        self._agent_id = agent_id

    def get_state(self) -> dict | None:
        """Serialize scratchpad for checkpointing."""
        return {"scratchpad": self._scratchpad}

    def set_state(self, state: dict) -> None:
        """Restore scratchpad from checkpoint."""
        self._scratchpad = state.get("scratchpad", "")

    def decide(self, observation: AgentObservation) -> AgentTurnResult:
        """Render prompt, call LLM, parse response into an action."""
        try:
            prompt = render_prompt(observation, self._scratchpad, self._agent_id)
            raw_response = self._backend.generate(prompt)
            action, scratchpad_update = parse_response(raw_response)

            # Update internal scratchpad if the LLM provided one
            if scratchpad_update is not None:
                self._scratchpad = scratchpad_update

            return AgentTurnResult(
                action=action,
                scratchpad_update=scratchpad_update,
            )
        except Exception:
            logger.warning(
                "LLMAgent %s decide() failed, using idle", self._agent_id, exc_info=True
            )
            return AgentTurnResult(action=IdleAction())

    async def decide_async(
        self, observation: AgentObservation, session: aiohttp.ClientSession
    ) -> AgentTurnResult:
        """Async version of decide() for parallel LLM inference."""
        try:
            prompt = render_prompt(observation, self._scratchpad, self._agent_id)
            raw_response = await self._backend.generate_async(prompt, session)
            action, scratchpad_update = parse_response(raw_response)

            if scratchpad_update is not None:
                self._scratchpad = scratchpad_update

            return AgentTurnResult(
                action=action,
                scratchpad_update=scratchpad_update,
            )
        except Exception:
            logger.warning(
                "LLMAgent %s decide_async() failed, using idle",
                self._agent_id,
                exc_info=True,
            )
            return AgentTurnResult(action=IdleAction())


class LLMAgentFactory(AgentFactory):
    """Creates LLMAgent instances sharing a single LLMBackend."""

    def __init__(self, backend: LLMBackend, config: SimulationConfig) -> None:
        self._backend = backend
        self._config = config

    def create_agent(self, agent_id: str) -> BaseAgent:
        """Create an LLMAgent and call on_spawn."""
        agent = LLMAgent(self._backend)
        agent.on_spawn(agent_id, self._config)
        return agent
