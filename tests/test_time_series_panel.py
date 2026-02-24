"""Tests for the time series panel credit reservoir computation."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from visualization.panels.time_series import _compute_credit_reservoirs

_MILLICREDITS_PER_CREDIT = 1000


@pytest.fixture()
def mock_config() -> dict:
    return {"total_credit_supply": 10_000_000}  # 10,000 display credits


@pytest.fixture()
def mock_snapshots() -> pd.DataFrame:
    """Two agents across 3 ticks."""
    return pd.DataFrame(
        [
            {"tick": 0, "agent_id": "agent_001", "credits": 30.0},
            {"tick": 0, "agent_id": "agent_002", "credits": 20.0},
            {"tick": 1, "agent_id": "agent_001", "credits": 25.0},
            {"tick": 1, "agent_id": "agent_002", "credits": 35.0},
            {"tick": 2, "agent_id": "agent_001", "credits": 40.0},
            {"tick": 2, "agent_id": "agent_002", "credits": 10.0},
        ]
    )


@pytest.fixture()
def mock_tick_metrics() -> pd.DataFrame:
    return pd.DataFrame({"tick": [0, 1, 2]})


class TestCreditReservoirs:
    def test_agent_and_system_sum_to_total(
        self, mock_config: dict, mock_snapshots: pd.DataFrame
    ) -> None:
        with (
            patch(
                "visualization.panels.time_series.data.load_config",
                return_value=mock_config,
            ),
            patch(
                "visualization.panels.time_series.data.load_agent_snapshots",
                return_value=mock_snapshots,
            ),
        ):
            result = _compute_credit_reservoirs("fake.db", "fake_dir", 0, 2)

        total_supply = mock_config["total_credit_supply"] / _MILLICREDITS_PER_CREDIT
        for tick in [0, 1, 2]:
            tick_data = result[result["tick"] == tick]
            assert abs(tick_data["credits"].sum() - total_supply) < 0.01

    def test_agent_credits_correct(
        self, mock_config: dict, mock_snapshots: pd.DataFrame
    ) -> None:
        with (
            patch(
                "visualization.panels.time_series.data.load_config",
                return_value=mock_config,
            ),
            patch(
                "visualization.panels.time_series.data.load_agent_snapshots",
                return_value=mock_snapshots,
            ),
        ):
            result = _compute_credit_reservoirs("fake.db", "fake_dir", 0, 2)

        agent_rows = result[result["reservoir"] == "Agent Credits"]
        # tick 0: 30 + 20 = 50
        assert agent_rows[agent_rows["tick"] == 0]["credits"].iloc[0] == 50.0
        # tick 1: 25 + 35 = 60
        assert agent_rows[agent_rows["tick"] == 1]["credits"].iloc[0] == 60.0
        # tick 2: 40 + 10 = 50
        assert agent_rows[agent_rows["tick"] == 2]["credits"].iloc[0] == 50.0

    def test_tick_range_filtering(
        self, mock_config: dict, mock_snapshots: pd.DataFrame
    ) -> None:
        with (
            patch(
                "visualization.panels.time_series.data.load_config",
                return_value=mock_config,
            ),
            patch(
                "visualization.panels.time_series.data.load_agent_snapshots",
                return_value=mock_snapshots,
            ),
        ):
            result = _compute_credit_reservoirs("fake.db", "fake_dir", 1, 2)

        ticks = result["tick"].unique()
        assert 0 not in ticks
        assert 1 in ticks
        assert 2 in ticks

    def test_empty_snapshots(
        self, mock_config: dict, mock_tick_metrics: pd.DataFrame
    ) -> None:
        with (
            patch(
                "visualization.panels.time_series.data.load_config",
                return_value=mock_config,
            ),
            patch(
                "visualization.panels.time_series.data.load_agent_snapshots",
                return_value=pd.DataFrame(),
            ),
            patch(
                "visualization.panels.time_series.data.load_tick_metrics",
                return_value=mock_tick_metrics,
            ),
        ):
            result = _compute_credit_reservoirs("fake.db", "fake_dir", 0, 2)

        total_supply = mock_config["total_credit_supply"] / _MILLICREDITS_PER_CREDIT
        agent_rows = result[result["reservoir"] == "Agent Credits"]
        system_rows = result[result["reservoir"] == "System Credits"]
        assert (agent_rows["credits"] == 0.0).all()
        assert (system_rows["credits"] == total_supply).all()
