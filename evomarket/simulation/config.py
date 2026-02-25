"""Simulation configuration — user-facing config with credit-to-millicredit conversion."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from typing import Literal

from evomarket.core.types import MILLICREDITS_PER_CREDIT
from evomarket.core.world import WorldConfig


def _default_agent_mix() -> dict[str, int]:
    return {
        "harvester": 6,
        "trader": 5,
        "social": 4,
        "hoarder": 3,
        "explorer": 2,
    }


@dataclass
class SimulationConfig:
    """User-facing simulation configuration.

    Credit values are in display credits (floats). They are converted to
    millicredits (integers) when constructing a WorldConfig.
    """

    # World
    seed: int = 42
    num_nodes: int = 15
    num_commodity_types: int = 4
    total_credit_supply: float = 10_000.0

    # Economy
    survival_tax: float = 0.5
    starting_credits: float = 50.0
    npc_base_price: float = 5.0
    npc_stockpile_capacity: int = 50
    npc_budget_replenish_rate: float = 30.0
    npc_stockpile_decay_rate: float = 0.1
    treasury_min_reserve: float = 100.0
    resource_spawn_rate: float = 1.0
    node_resource_cap: int = 20

    # Population
    population_size: int = 20
    spawn_grace_period: int = 5

    # Trading
    max_open_orders: int = 10
    max_pending_trades: int = 3

    # Death
    death_treasury_return_pct: float = 0.5
    death_local_share_pct: float = 0.5

    # Simulation
    ticks_per_episode: int = 500
    checkpoint_interval: int = 50
    mode: Literal["synchronous", "asynchronous"] = "synchronous"

    # Agents
    agent_mix: dict[str, int] = field(default_factory=_default_agent_mix)
    llm_backends: dict[str, dict] = field(default_factory=dict)

    # Debug
    verify_invariant_every_phase: bool = False
    verbose_logging: bool = False

    def __post_init__(self) -> None:
        """Validate configuration."""
        mix_total = sum(self.agent_mix.values())
        if mix_total != self.population_size:
            raise ValueError(
                f"agent_mix sum ({mix_total}) must equal "
                f"population_size ({self.population_size})"
            )

        valid_types = {
            "harvester",
            "trader",
            "social",
            "hoarder",
            "explorer",
            "random",
            "llm",
        }
        for agent_type in self.agent_mix:
            if agent_type in valid_types:
                continue
            if agent_type.startswith("llm:"):
                backend_name = agent_type[4:]
                if backend_name not in self.llm_backends:
                    raise ValueError(
                        f"agent_mix references 'llm:{backend_name}' but no "
                        f"matching entry in llm_backends. "
                        f"Available backends: {sorted(self.llm_backends)}"
                    )
                continue
            raise ValueError(
                f"Unknown agent type in agent_mix: {agent_type!r}. "
                f"Valid types: {sorted(valid_types)} or 'llm:<backend_name>'"
            )

        if self.total_credit_supply < self.starting_credits * self.population_size:
            raise ValueError(
                f"total_credit_supply ({self.total_credit_supply}) insufficient "
                f"to fund {self.population_size} agents at "
                f"{self.starting_credits} credits each"
            )

        if self.ticks_per_episode < 1:
            raise ValueError("ticks_per_episode must be >= 1")

        if self.checkpoint_interval < 0:
            raise ValueError("checkpoint_interval must be >= 0")

    def _to_mc(self, credits: float) -> int:
        """Convert display credits to millicredits."""
        return round(credits * MILLICREDITS_PER_CREDIT)

    def to_world_config(self) -> WorldConfig:
        """Construct a WorldConfig with millicredit values."""
        return WorldConfig(
            num_nodes=self.num_nodes,
            num_commodity_types=self.num_commodity_types,
            total_credit_supply=self._to_mc(self.total_credit_supply),
            starting_credits=self._to_mc(self.starting_credits),
            population_size=self.population_size,
            resource_spawn_rate=self.resource_spawn_rate,
            node_resource_cap=self.node_resource_cap,
            npc_base_price=self._to_mc(self.npc_base_price),
            npc_stockpile_capacity=self.npc_stockpile_capacity,
            npc_budget_replenish_rate=self._to_mc(self.npc_budget_replenish_rate),
            npc_stockpile_decay_rate=self.npc_stockpile_decay_rate,
            survival_tax=self._to_mc(self.survival_tax),
            spawn_grace_period=self.spawn_grace_period,
            ticks_per_episode=self.ticks_per_episode,
            max_open_orders=self.max_open_orders,
            max_pending_trades=self.max_pending_trades,
            death_treasury_return_pct=self.death_treasury_return_pct,
            death_local_share_pct=self.death_local_share_pct,
            treasury_min_reserve=self._to_mc(self.treasury_min_reserve),
        )

    def to_json(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        result: dict = {}
        for f in fields(self):
            result[f.name] = getattr(self, f.name)
        return result

    @classmethod
    def from_json(cls, data: dict) -> SimulationConfig:
        """Deserialize from a JSON-compatible dict."""
        return cls(**data)

    def to_json_string(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_json(), indent=2)

    @classmethod
    def from_json_string(cls, s: str) -> SimulationConfig:
        """Deserialize from a JSON string."""
        return cls.from_json(json.loads(s))
