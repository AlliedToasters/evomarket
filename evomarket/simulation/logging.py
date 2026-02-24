"""Event logging — SQLite-backed structured event storage."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evomarket.core.world import WorldState
    from evomarket.engine.actions import ActionResult
    from evomarket.engine.inheritance import DeathResult
    from evomarket.engine.tick import TickMetrics

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ticks (
    tick_number INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    metrics_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    tick INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    action_json TEXT NOT NULL,
    success INTEGER NOT NULL,
    detail TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    tick INTEGER NOT NULL,
    buyer_id TEXT NOT NULL,
    seller_id TEXT NOT NULL,
    trade_type TEXT NOT NULL,
    items_json TEXT NOT NULL,
    credits INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS deaths (
    tick INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    estate_json TEXT NOT NULL,
    will_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    tick INTEGER NOT NULL,
    sender_id TEXT NOT NULL,
    recipient TEXT NOT NULL,
    node_id TEXT NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_snapshots (
    tick INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    credits INTEGER NOT NULL,
    inventory_json TEXT NOT NULL,
    location TEXT NOT NULL,
    age INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_actions_tick ON actions(tick);
CREATE INDEX IF NOT EXISTS idx_trades_tick ON trades(tick);
CREATE INDEX IF NOT EXISTS idx_deaths_tick ON deaths(tick);
CREATE INDEX IF NOT EXISTS idx_messages_tick ON messages(tick);
CREATE INDEX IF NOT EXISTS idx_snapshots_tick ON agent_snapshots(tick);
CREATE INDEX IF NOT EXISTS idx_snapshots_agent ON agent_snapshots(agent_id);
"""


@dataclass
class _BufferedEvent:
    """A single buffered event waiting to be flushed."""

    table: str
    values: tuple


class EventLogger:
    """SQLite event logger with batched writes per tick.

    Args:
        db_path: Path to the SQLite database file.
        enabled: If False, all logging calls are no-ops.
    """

    def __init__(
        self, db_path: str | Path | None = None, *, enabled: bool = True
    ) -> None:
        self._enabled = enabled
        self._conn: sqlite3.Connection | None = None
        self._buffer: list[_BufferedEvent] = []

        if not enabled or db_path is None:
            self._enabled = False
            return

        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def log_tick(self, tick_number: int, metrics: TickMetrics) -> None:
        """Buffer a tick record."""
        if not self._enabled:
            return
        from datetime import datetime, timezone

        metrics_dict = {
            "total_credits_in_circulation": metrics.total_credits_in_circulation,
            "agent_credit_gini": metrics.agent_credit_gini,
            "total_trade_volume": metrics.total_trade_volume,
            "trades_executed": metrics.trades_executed,
            "agents_alive": metrics.agents_alive,
            "agents_died": metrics.agents_died,
            "agents_spawned": metrics.agents_spawned,
            "total_resources_harvested": metrics.total_resources_harvested,
            "total_npc_sales": metrics.total_npc_sales,
            "total_messages_sent": metrics.total_messages_sent,
        }
        self._buffer.append(
            _BufferedEvent(
                table="ticks",
                values=(
                    tick_number,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(metrics_dict),
                ),
            )
        )

    def log_actions(self, tick: int, action_results: list[ActionResult]) -> None:
        """Buffer action records."""
        if not self._enabled:
            return
        for r in action_results:
            action_dict = r.action.model_dump(mode="json")
            self._buffer.append(
                _BufferedEvent(
                    table="actions",
                    values=(
                        tick,
                        r.agent_id,
                        r.action.action_type,
                        json.dumps(action_dict),
                        1 if r.success else 0,
                        r.detail,
                    ),
                )
            )

    def log_trades(self, tick: int, action_results: list[ActionResult]) -> None:
        """Buffer trade records from successful trade actions."""
        if not self._enabled:
            return
        for r in action_results:
            if not r.success:
                continue
            if r.action.action_type == "accept_order":
                self._buffer.append(
                    _BufferedEvent(
                        table="trades",
                        values=(
                            tick,
                            r.agent_id,  # buyer/acceptor
                            "",  # seller unknown from ActionResult
                            "order",
                            "{}",
                            r.credits_transferred,
                        ),
                    )
                )
            elif r.action.action_type == "accept_trade":
                self._buffer.append(
                    _BufferedEvent(
                        table="trades",
                        values=(
                            tick,
                            r.agent_id,
                            "",
                            "p2p",
                            "{}",
                            r.credits_transferred,
                        ),
                    )
                )
            elif r.npc_sale:
                self._buffer.append(
                    _BufferedEvent(
                        table="trades",
                        values=(
                            tick,
                            "npc",
                            r.agent_id,
                            "npc",
                            "{}",
                            r.credits_transferred,
                        ),
                    )
                )

    def log_deaths(self, tick: int, death_results: list[DeathResult]) -> None:
        """Buffer death records."""
        if not self._enabled:
            return
        for d in death_results:
            estate = {
                "credits": d.total_estate_credits,
                "inventory": {
                    k.value if hasattr(k, "value") else str(k): v
                    for k, v in d.total_estate_commodities.items()
                },
            }
            will_data = [
                {"beneficiary": w.beneficiary_id, "credits": w.credits}
                for w in d.will_distributions
            ]
            self._buffer.append(
                _BufferedEvent(
                    table="deaths",
                    values=(
                        tick,
                        d.agent_id,
                        json.dumps(estate),
                        json.dumps(will_data),
                    ),
                )
            )

    def log_messages(self, tick: int, action_results: list[ActionResult]) -> None:
        """Buffer message records from successful send_message actions."""
        if not self._enabled:
            return
        for r in action_results:
            if not r.success or r.action.action_type != "send_message":
                continue
            self._buffer.append(
                _BufferedEvent(
                    table="messages",
                    values=(
                        tick,
                        r.agent_id,
                        getattr(r.action, "target", ""),
                        "",  # node_id not available from ActionResult
                        getattr(r.action, "text", ""),
                    ),
                )
            )

    def log_agent_snapshots(self, tick: int, world: WorldState) -> None:
        """Buffer per-agent snapshots for all living agents."""
        if not self._enabled:
            return
        for agent_id, agent in world.agents.items():
            if not agent.alive:
                continue
            inv = {
                k.value if hasattr(k, "value") else str(k): v
                for k, v in agent.inventory.items()
            }
            self._buffer.append(
                _BufferedEvent(
                    table="agent_snapshots",
                    values=(
                        tick,
                        agent_id,
                        agent.credits,
                        json.dumps(inv),
                        agent.location,
                        agent.age,
                    ),
                )
            )

    def flush_tick(self) -> None:
        """Commit all buffered events in a single transaction."""
        if not self._enabled or not self._buffer or self._conn is None:
            self._buffer.clear()
            return

        _INSERT_SQL = {
            "ticks": "INSERT INTO ticks (tick_number, timestamp, metrics_json) VALUES (?, ?, ?)",
            "actions": "INSERT INTO actions (tick, agent_id, action_type, action_json, success, detail) VALUES (?, ?, ?, ?, ?, ?)",
            "trades": "INSERT INTO trades (tick, buyer_id, seller_id, trade_type, items_json, credits) VALUES (?, ?, ?, ?, ?, ?)",
            "deaths": "INSERT INTO deaths (tick, agent_id, estate_json, will_json) VALUES (?, ?, ?, ?)",
            "messages": "INSERT INTO messages (tick, sender_id, recipient, node_id, text) VALUES (?, ?, ?, ?, ?)",
            "agent_snapshots": "INSERT INTO agent_snapshots (tick, agent_id, credits, inventory_json, location, age) VALUES (?, ?, ?, ?, ?, ?)",
        }

        cursor = self._conn.cursor()
        try:
            cursor.execute("BEGIN")
            for event in self._buffer:
                cursor.execute(_INSERT_SQL[event.table], event.values)
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise
        finally:
            self._buffer.clear()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection | None:
        """Access the underlying connection (for queries)."""
        return self._conn
