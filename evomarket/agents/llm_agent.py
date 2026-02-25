"""LLM-backed agent — uses a language model to decide actions each tick."""

from __future__ import annotations

import logging
import time
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

    def __init__(self, backend: LLMBackend, agent_type_label: str = "llm") -> None:
        self._backend = backend
        self._agent_id: str = ""
        self._scratchpad: str = ""
        self.agent_type_label = agent_type_label

    def on_spawn(self, agent_id: str, config: SimulationConfig) -> None:
        """Store agent ID for prompt rendering."""
        self._agent_id = agent_id

    def get_state(self) -> dict | None:
        """Serialize scratchpad for checkpointing."""
        return {"scratchpad": self._scratchpad}

    def set_state(self, state: dict) -> None:
        """Restore scratchpad from checkpoint."""
        self._scratchpad = state.get("scratchpad", "")

    @property
    def model_tag(self) -> str:
        """Short identifier: model name for logging."""
        return self._backend.model

    def _log_decide(self, raw_response: str, action: object, elapsed: float) -> None:
        """Log per-call diagnostics tagged with model and agent ID."""
        model = self.model_tag
        action_name = type(action).__name__
        if not raw_response or not raw_response.strip():
            logger.warning(
                "[%s] %s: empty response (%.1fs) → idle",
                model,
                self._agent_id,
                elapsed,
            )
        elif action_name == "IdleAction" and raw_response.strip():
            # Got a response but couldn't parse an action
            snippet = raw_response.strip()[:120].replace("\n", " ")
            logger.warning(
                "[%s] %s: parse failed (%.1fs) → idle. Response: %s",
                model,
                self._agent_id,
                elapsed,
                snippet,
            )
        else:
            logger.info(
                "[%s] %s: %s (%.1fs)",
                model,
                self._agent_id,
                action_name,
                elapsed,
            )

    def decide(self, observation: AgentObservation) -> AgentTurnResult:
        """Render prompt, call LLM, parse response into an action."""
        try:
            prompt = render_prompt(observation, self._scratchpad, self._agent_id)
            t0 = time.monotonic()
            raw_response = self._backend.generate(prompt)
            elapsed = time.monotonic() - t0
            action, scratchpad_update = parse_response(raw_response)

            self._log_decide(raw_response, action, elapsed)

            # Update internal scratchpad if the LLM provided one
            if scratchpad_update is not None:
                self._scratchpad = scratchpad_update

            return AgentTurnResult(
                action=action,
                scratchpad_update=scratchpad_update,
            )
        except Exception:
            logger.warning(
                "[%s] %s: decide() exception, using idle",
                self.model_tag,
                self._agent_id,
                exc_info=True,
            )
            return AgentTurnResult(action=IdleAction())

    async def decide_async(
        self, observation: AgentObservation, session: aiohttp.ClientSession
    ) -> AgentTurnResult:
        """Async version of decide() for parallel LLM inference."""
        try:
            prompt = render_prompt(observation, self._scratchpad, self._agent_id)
            t0 = time.monotonic()
            raw_response = await self._backend.generate_async(prompt, session)
            elapsed = time.monotonic() - t0
            action, scratchpad_update = parse_response(raw_response)

            self._log_decide(raw_response, action, elapsed)

            if scratchpad_update is not None:
                self._scratchpad = scratchpad_update

            return AgentTurnResult(
                action=action,
                scratchpad_update=scratchpad_update,
            )
        except Exception:
            logger.warning(
                "[%s] %s: decide_async() exception, using idle",
                self.model_tag,
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


class MixedAgentFactory(AgentFactory):
    """Creates a mix of heuristic, random, and LLM agents based on agent_mix config.

    Supports agent types: heuristic archetypes (harvester, trader, etc.),
    ``"random"``, ``"llm"`` (bare), and ``"llm:<name>"`` (named backend).
    """

    def __init__(
        self,
        config: SimulationConfig,
        llm_backends: dict[str, LLMBackend] | None = None,
    ) -> None:
        self._config = config
        self._llm_backends = llm_backends or {}
        self._base_seed = config.seed

        # Build round-robin type sequence (same pattern as HeuristicAgentFactory)
        self._type_sequence: list[str] = []
        for agent_type, count in config.agent_mix.items():
            self._type_sequence.extend([agent_type] * count)
        self._next_index = 0

    def create_agent(self, agent_id: str) -> BaseAgent:
        """Create the next agent in the round-robin sequence."""
        from evomarket.agents.heuristic_agent import _AGENT_CLASSES
        from evomarket.agents.random_agent import RandomAgent

        if self._next_index < len(self._type_sequence):
            agent_type = self._type_sequence[self._next_index]
        else:
            agent_type = self._type_sequence[
                self._next_index % len(self._type_sequence)
            ]
        self._next_index += 1

        seed = hash((self._base_seed, agent_id)) & 0xFFFFFFFF

        # LLM agent: bare "llm" or named "llm:<name>"
        if agent_type == "llm" or agent_type.startswith("llm:"):
            if agent_type == "llm":
                backend_name = ""
            else:
                backend_name = agent_type[4:]
            backend = self._llm_backends.get(backend_name)
            if backend is None:
                raise ValueError(
                    f"No LLM backend configured for {agent_type!r}. "
                    f"Available: {sorted(self._llm_backends)}"
                )
            agent: BaseAgent = LLMAgent(backend, agent_type_label=agent_type)
            agent.on_spawn(agent_id, self._config)
            return agent

        # Random agent
        if agent_type == "random":
            agent = RandomAgent(seed=seed)
            agent.on_spawn(agent_id, self._config)
            return agent

        # Heuristic agent
        agent_cls = _AGENT_CLASSES.get(agent_type)
        if agent_cls is None:
            from evomarket.agents.heuristic_agent import HarvesterAgent

            agent_cls = HarvesterAgent
        agent = agent_cls(seed=seed)
        agent.on_spawn(agent_id, self._config)
        return agent
