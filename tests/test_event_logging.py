"""Tests for EventLogger."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from evomarket.core.types import CommodityType
from evomarket.engine.actions import (
    ActionResult,
    HarvestAction,
    IdleAction,
    SendMessageAction,
)
from evomarket.engine.tick import TickMetrics
from evomarket.simulation.logging import EventLogger


def _make_tick_metrics(**overrides: int | float) -> TickMetrics:
    defaults = dict(
        total_credits_in_circulation=500_000,
        agent_credit_gini=0.3,
        total_trade_volume=10_000,
        trades_executed=5,
        agents_alive=18,
        agents_died=1,
        agents_spawned=1,
        total_resources_harvested=10,
        total_npc_sales=3,
        total_messages_sent=2,
    )
    defaults.update(overrides)
    return TickMetrics(**defaults)  # type: ignore[arg-type]


class TestEventLoggerCreation:
    def test_creates_database(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        assert db_path.exists()
        logger.close()

    def test_creates_all_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        expected = {
            "ticks",
            "actions",
            "trades",
            "deaths",
            "messages",
            "agent_snapshots",
        }
        assert expected.issubset(tables)
        conn.close()
        logger.close()

    def test_wal_mode(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        assert logger.connection is not None
        cursor = logger.connection.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode == "wal"
        logger.close()


class TestNoOpMode:
    def test_no_database_created(self, tmp_path: Path) -> None:
        db_path = tmp_path / "noop.sqlite"
        logger = EventLogger(db_path, enabled=False)
        assert not db_path.exists()
        logger.close()

    def test_log_calls_are_noop(self) -> None:
        logger = EventLogger(enabled=False)
        metrics = _make_tick_metrics()
        logger.log_tick(0, metrics)
        logger.log_actions(0, [])
        logger.log_trades(0, [])
        logger.log_messages(0, [])
        logger.flush_tick()
        logger.close()


class TestBatchedWrites:
    def test_tick_logged(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        metrics = _make_tick_metrics()
        logger.log_tick(0, metrics)
        logger.flush_tick()

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM ticks").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 0  # tick_number
        data = json.loads(rows[0][2])
        assert data["agents_alive"] == 18
        conn.close()
        logger.close()

    def test_actions_logged(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        results = [
            ActionResult(
                agent_id="agent_001",
                action=HarvestAction(),
                success=True,
                detail="Harvested 1 IRON",
            ),
            ActionResult(
                agent_id="agent_002",
                action=IdleAction(),
                success=True,
                detail="Idle",
            ),
        ]
        logger.log_actions(0, results)
        logger.flush_tick()

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM actions ORDER BY agent_id").fetchall()
        assert len(rows) == 2
        assert rows[0][1] == "agent_001"
        assert rows[0][2] == "harvest"
        conn.close()
        logger.close()

    def test_messages_logged(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        results = [
            ActionResult(
                agent_id="agent_001",
                action=SendMessageAction(target="broadcast", text="hello"),
                success=True,
                detail="Broadcast message",
            ),
        ]
        logger.log_messages(0, results)
        logger.flush_tick()

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM messages").fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "agent_001"
        assert rows[0][4] == "hello"
        conn.close()
        logger.close()

    def test_buffer_cleared_after_flush(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        logger.log_tick(0, _make_tick_metrics())
        logger.flush_tick()
        # Second flush should be no-op
        logger.flush_tick()

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM ticks").fetchall()
        assert len(rows) == 1
        conn.close()
        logger.close()

    def test_multiple_ticks(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.sqlite"
        logger = EventLogger(db_path)
        for i in range(5):
            logger.log_tick(i, _make_tick_metrics())
            logger.flush_tick()

        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM ticks").fetchall()
        assert len(rows) == 5
        conn.close()
        logger.close()
