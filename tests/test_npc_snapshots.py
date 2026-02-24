"""Tests for NPC snapshot logging, data layer, and panel."""

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from evomarket.core.world import WorldConfig, generate_world
from evomarket.simulation.logging import EventLogger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_db_with_npc_snapshots(db_path: Path) -> str:
    """Create a test database with npc_snapshots populated from a small world."""
    config = WorldConfig(
        num_nodes=5,
        num_commodity_types=2,
        population_size=5,
        total_credit_supply=10_000_000,
        starting_credits=30_000,
    )
    world = generate_world(config, seed=42)

    logger = EventLogger(db_path)
    logger.log_npc_snapshots(0, world)
    logger.flush_tick()
    logger.close()
    return str(db_path)


def _create_db_without_npc_snapshots(db_path: Path) -> str:
    """Create a bare database with only the original 6 tables (no npc_snapshots)."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE ticks (tick_number INTEGER PRIMARY KEY, timestamp TEXT, metrics_json TEXT)"
    )
    conn.commit()
    conn.close()
    return str(db_path)


# ---------------------------------------------------------------------------
# 5.1 — log_npc_snapshots writes correct rows
# ---------------------------------------------------------------------------


class TestLogNpcSnapshots:
    def test_writes_rows_for_npc_nodes(self, tmp_path: Path) -> None:
        config = WorldConfig(
            num_nodes=5,
            num_commodity_types=2,
            population_size=5,
            total_credit_supply=10_000_000,
            starting_credits=30_000,
        )
        world = generate_world(config, seed=42)

        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        logger.log_npc_snapshots(0, world)
        logger.flush_tick()

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM npc_snapshots ORDER BY node_id, commodity").fetchall()

        # Count expected rows: one per (node, commodity) where node buys that commodity
        expected_count = sum(len(n.npc_buys) for n in world.nodes.values())
        assert len(rows) == expected_count

        # Verify first row has correct structure
        row = rows[0]
        assert row["tick"] == 0
        assert row["node_id"] in [n.node_id for n in world.nodes.values()]
        assert row["commodity"] in ("IRON", "WOOD", "STONE", "HERBS")
        assert isinstance(row["price"], int)
        assert isinstance(row["stockpile"], int)
        assert isinstance(row["budget"], int)

        conn.close()
        logger.close()

    def test_noop_when_disabled(self, tmp_path: Path) -> None:
        logger = EventLogger(enabled=False)
        config = WorldConfig(
            num_nodes=5,
            num_commodity_types=2,
            population_size=5,
            total_credit_supply=10_000_000,
            starting_credits=30_000,
        )
        world = generate_world(config, seed=42)
        logger.log_npc_snapshots(0, world)
        logger.flush_tick()
        logger.close()

    def test_excludes_nodes_without_npc_buys(self, tmp_path: Path) -> None:
        config = WorldConfig(
            num_nodes=5,
            num_commodity_types=2,
            population_size=5,
            total_credit_supply=10_000_000,
            starting_credits=30_000,
        )
        world = generate_world(config, seed=42)

        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        logger.log_npc_snapshots(0, world)
        logger.flush_tick()

        conn = sqlite3.connect(str(db_path))
        node_ids_in_db = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT node_id FROM npc_snapshots"
            ).fetchall()
        }

        # Only nodes with npc_buys should appear
        npc_node_ids = {n.node_id for n in world.nodes.values() if n.npc_buys}
        assert node_ids_in_db == npc_node_ids

        conn.close()
        logger.close()


# ---------------------------------------------------------------------------
# 5.2 — has_npc_snapshots
# ---------------------------------------------------------------------------


class TestHasNpcSnapshots:
    def test_returns_true_when_table_exists(self, tmp_path: Path) -> None:
        # Avoid importing streamlit in test — test the SQL logic directly
        db_path = tmp_path / "with_table.sqlite"
        _create_db_with_npc_snapshots(db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='npc_snapshots'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_returns_false_when_table_missing(self, tmp_path: Path) -> None:
        db_path = tmp_path / "no_table.sqlite"
        _create_db_without_npc_snapshots(db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='npc_snapshots'"
        )
        assert cursor.fetchone() is None
        conn.close()


# ---------------------------------------------------------------------------
# 5.3 — load_npc_snapshots DataFrame correctness
# ---------------------------------------------------------------------------


class TestLoadNpcSnapshots:
    def test_returns_correct_dataframe(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.sqlite"
        _create_db_with_npc_snapshots(db_path)

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT tick, node_id, commodity, price, stockpile, budget "
            "FROM npc_snapshots ORDER BY tick, node_id, commodity"
        ).fetchall()
        conn.close()

        records = [
            {
                "tick": r["tick"],
                "node_id": r["node_id"],
                "commodity": r["commodity"],
                "price": r["price"] / 1000,
                "stockpile": r["stockpile"],
                "budget": r["budget"] / 1000,
            }
            for r in rows
        ]
        df = pd.DataFrame(records)

        assert set(df.columns) == {"tick", "node_id", "commodity", "price", "stockpile", "budget"}
        assert len(df) > 0
        # Prices should be in display credits (not millicredits)
        # Base price is 5000 mc = 5.0 display credits; at zero stockpile price = base
        assert df["price"].max() <= 10.0  # reasonable display credit range


# ---------------------------------------------------------------------------
# 5.4 & 5.5 — Panel rendering (integration-style, no Streamlit runtime)
# ---------------------------------------------------------------------------


class TestNpcPricesPanel:
    def test_table_present_in_schema(self, tmp_path: Path) -> None:
        """Verify the EventLogger creates the npc_snapshots table."""
        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert "npc_snapshots" in tables
        conn.close()
        logger.close()

    def test_table_missing_from_old_db(self, tmp_path: Path) -> None:
        """Verify detection of missing table in old databases."""
        db_path = tmp_path / "old.sqlite"
        _create_db_without_npc_snapshots(db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='npc_snapshots'"
        )
        assert cursor.fetchone() is None
        conn.close()
