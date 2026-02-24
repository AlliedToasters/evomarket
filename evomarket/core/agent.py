"""Agent state model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from evomarket.core.types import CommodityType, Millicredits


class Agent(BaseModel):
    """An agent in the game world."""

    model_config = ConfigDict(frozen=False)

    agent_id: str
    display_name: str
    location: str
    credits: Millicredits
    inventory: dict[CommodityType, int]
    age: int = 0
    alive: bool = True
    will: dict[str, float]
    prompt_document: str = ""
    grace_ticks_remaining: int = 0

    @field_validator("inventory")
    @classmethod
    def _validate_inventory(
        cls, v: dict[CommodityType, int]
    ) -> dict[CommodityType, int]:
        for commodity, qty in v.items():
            if qty < 0:
                raise ValueError(
                    f"Inventory for {commodity} must be non-negative, got {qty}"
                )
        return v

    @field_validator("will")
    @classmethod
    def _validate_will(cls, v: dict[str, float]) -> dict[str, float]:
        for agent_id, pct in v.items():
            if pct < 0:
                raise ValueError(
                    f"Will percentage for {agent_id} must be non-negative, got {pct}"
                )
        total = sum(v.values())
        if total > 1.0 + 1e-9:
            raise ValueError(f"Will percentages sum to {total}, must be ≤ 1.0")
        return v
