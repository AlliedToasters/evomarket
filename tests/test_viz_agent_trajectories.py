"""Tests for the Agent Wealth Trajectories panel and supporting data functions."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def episode_dir(tmp_path: Path) -> Path:
    """Create a minimal episode directory with SQLite DB and result.json."""
    db_path = tmp_path / "episode.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE agent_snapshots "
        "(tick INTEGER, agent_id TEXT, credits INTEGER, "
        "inventory_json TEXT, location TEXT, age INTEGER)"
    )
    conn.execute(
        "CREATE TABLE ticks (tick_number INTEGER PRIMARY KEY, timestamp TEXT, metrics_json TEXT)"
    )
    # Insert snapshot data for two agents over 3 ticks
    snapshots = [
        (0, "agent_001", 30000, '{"IRON":0}', "node_0", 0),
        (0, "agent_002", 30000, '{"IRON":0}', "node_1", 0),
        (1, "agent_001", 35000, '{"IRON":1}', "node_0", 1),
        (1, "agent_002", 25000, '{"IRON":0}', "node_1", 1),
        (2, "agent_001", 40000, '{"IRON":2}', "node_0", 2),
        (2, "agent_002", 20000, '{"IRON":0}', "node_1", 2),
    ]
    conn.executemany(
        "INSERT INTO agent_snapshots VALUES (?,?,?,?,?,?)", snapshots
    )
    conn.commit()
    conn.close()

    result = {
        "agent_summaries": [
            {
                "agent_id": "agent_001",
                "agent_type": "HarvesterAgent",
                "final_credits": 40000,
                "final_net_worth": 42000,
                "lifetime": 100,
                "total_trades": 5,
                "total_messages": 2,
                "cause_of_death": None,
            },
            {
                "agent_id": "agent_002",
                "agent_type": "TraderAgent",
                "final_credits": 20000,
                "final_net_worth": 21000,
                "lifetime": 50,
                "total_trades": 10,
                "total_messages": 3,
                "cause_of_death": "starvation",
            },
        ]
    }
    (tmp_path / "result.json").write_text(json.dumps(result))
    return tmp_path


@pytest.fixture
def empty_episode_dir(tmp_path: Path) -> Path:
    """Create an episode directory with an empty DB and no result.json."""
    db_path = tmp_path / "episode.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE agent_snapshots "
        "(tick INTEGER, agent_id TEXT, credits INTEGER, "
        "inventory_json TEXT, location TEXT, age INTEGER)"
    )
    conn.commit()
    conn.close()
    return tmp_path


# ---------------------------------------------------------------------------
# Tests for load_agent_summaries
# ---------------------------------------------------------------------------


class TestLoadAgentSummaries:
    def test_columns(self, episode_dir: Path) -> None:
        from visualization.data import load_agent_summaries

        load_agent_summaries.clear()
        df = load_agent_summaries(str(episode_dir))
        expected = [
            "agent_id",
            "agent_type",
            "net_worth",
            "lifetime",
            "total_trades",
            "final_credits",
            "cause_of_death",
        ]
        assert list(df.columns) == expected

    def test_type_normalization(self, episode_dir: Path) -> None:
        from visualization.data import load_agent_summaries

        load_agent_summaries.clear()
        df = load_agent_summaries(str(episode_dir))
        assert df.loc[df["agent_id"] == "agent_001", "agent_type"].iloc[0] == "harvester"
        assert df.loc[df["agent_id"] == "agent_002", "agent_type"].iloc[0] == "trader"

    def test_credit_conversion(self, episode_dir: Path) -> None:
        from visualization.data import load_agent_summaries

        load_agent_summaries.clear()
        df = load_agent_summaries(str(episode_dir))
        row = df.loc[df["agent_id"] == "agent_001"].iloc[0]
        assert row["final_credits"] == pytest.approx(40.0)
        assert row["net_worth"] == pytest.approx(42.0)

    def test_missing_result_json(self, empty_episode_dir: Path) -> None:
        from visualization.data import load_agent_summaries

        load_agent_summaries.clear()
        df = load_agent_summaries(str(empty_episode_dir))
        assert df.empty
        expected = [
            "agent_id",
            "agent_type",
            "net_worth",
            "lifetime",
            "total_trades",
            "final_credits",
            "cause_of_death",
        ]
        assert list(df.columns) == expected

    def test_row_count(self, episode_dir: Path) -> None:
        from visualization.data import load_agent_summaries

        load_agent_summaries.clear()
        df = load_agent_summaries(str(episode_dir))
        assert len(df) == 2
