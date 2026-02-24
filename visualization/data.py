"""Centralized data access layer for the EvoMarket visualization dashboard.

All SQLite queries, DataFrame construction, and caching live here.
Panels should never query SQLite directly — import from this module instead.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

_MILLICREDITS_PER_CREDIT = 1000


@st.cache_resource
def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a read-only SQLite connection, cached per Streamlit session."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data
def load_tick_metrics(db_path: str) -> pd.DataFrame:
    """Load per-tick metrics with JSON unpacked and credits converted."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT tick_number, metrics_json FROM ticks ORDER BY tick_number"
    ).fetchall()

    records = []
    for row in rows:
        metrics = json.loads(row["metrics_json"])
        records.append(
            {
                "tick": row["tick_number"],
                "total_credits_in_circulation": metrics["total_credits_in_circulation"]
                / _MILLICREDITS_PER_CREDIT,
                "agent_credit_gini": metrics["agent_credit_gini"],
                "total_trade_volume": metrics["total_trade_volume"]
                / _MILLICREDITS_PER_CREDIT,
                "trades_executed": metrics["trades_executed"],
                "agents_alive": metrics["agents_alive"],
                "agents_died": metrics["agents_died"],
                "agents_spawned": metrics["agents_spawned"],
                "total_resources_harvested": metrics["total_resources_harvested"],
                "total_npc_sales": metrics["total_npc_sales"],
                "total_messages_sent": metrics["total_messages_sent"],
            }
        )
    return pd.DataFrame(records)


@st.cache_data
def load_agent_snapshots(db_path: str) -> pd.DataFrame:
    """Load per-agent-per-tick snapshots with inventory unpacked and credits converted."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT tick, agent_id, credits, inventory_json, location, age "
        "FROM agent_snapshots ORDER BY tick, agent_id"
    ).fetchall()

    records = []
    for row in rows:
        inv = json.loads(row["inventory_json"])
        records.append(
            {
                "tick": row["tick"],
                "agent_id": row["agent_id"],
                "credits": row["credits"] / _MILLICREDITS_PER_CREDIT,
                "inventory_IRON": inv.get("IRON", 0),
                "inventory_WOOD": inv.get("WOOD", 0),
                "inventory_STONE": inv.get("STONE", 0),
                "inventory_HERBS": inv.get("HERBS", 0),
                "location": row["location"],
                "age": row["age"],
            }
        )
    return pd.DataFrame(records)


@st.cache_data
def load_trades(db_path: str) -> pd.DataFrame:
    """Load all trades with credits converted to display credits."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT tick, buyer_id, seller_id, trade_type, credits "
        "FROM trades ORDER BY tick"
    ).fetchall()

    records = [
        {
            "tick": row["tick"],
            "buyer_id": row["buyer_id"],
            "seller_id": row["seller_id"],
            "trade_type": row["trade_type"],
            "credits": row["credits"] / _MILLICREDITS_PER_CREDIT,
        }
        for row in rows
    ]
    return pd.DataFrame(records)


@st.cache_data
def load_deaths(db_path: str) -> pd.DataFrame:
    """Load all deaths with estate JSON unpacked and credits converted."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT tick, agent_id, estate_json FROM deaths ORDER BY tick"
    ).fetchall()

    records = []
    for row in rows:
        estate = json.loads(row["estate_json"])
        inv = estate.get("inventory", {})
        records.append(
            {
                "tick": row["tick"],
                "agent_id": row["agent_id"],
                "estate_credits": estate.get("credits", 0) / _MILLICREDITS_PER_CREDIT,
                "estate_IRON": inv.get("IRON", 0),
                "estate_WOOD": inv.get("WOOD", 0),
                "estate_STONE": inv.get("STONE", 0),
                "estate_HERBS": inv.get("HERBS", 0),
            }
        )
    return pd.DataFrame(records)


@st.cache_data
def load_actions(db_path: str) -> pd.DataFrame:
    """Load all actions."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT tick, agent_id, action_type, success, detail "
        "FROM actions ORDER BY tick, agent_id"
    ).fetchall()

    records = [
        {
            "tick": row["tick"],
            "agent_id": row["agent_id"],
            "action_type": row["action_type"],
            "success": bool(row["success"]),
            "detail": row["detail"],
        }
        for row in rows
    ]
    return pd.DataFrame(records)


@st.cache_data
def load_messages(db_path: str) -> pd.DataFrame:
    """Load all messages."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT tick, sender_id, recipient, text FROM messages ORDER BY tick"
    ).fetchall()

    records = [
        {
            "tick": row["tick"],
            "sender_id": row["sender_id"],
            "recipient": row["recipient"],
            "text": row["text"],
        }
        for row in rows
    ]
    return pd.DataFrame(records)


def has_npc_snapshots(db_path: str) -> bool:
    """Check whether the npc_snapshots table exists in the database."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='npc_snapshots'"
    )
    return cursor.fetchone() is not None


@st.cache_data
def load_npc_snapshots(db_path: str) -> pd.DataFrame:
    """Load per-node-per-tick NPC state with prices/budgets converted to display credits."""
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT tick, node_id, commodity, price, stockpile, budget "
        "FROM npc_snapshots ORDER BY tick, node_id, commodity"
    ).fetchall()

    records = [
        {
            "tick": row["tick"],
            "node_id": row["node_id"],
            "commodity": row["commodity"],
            "price": row["price"] / _MILLICREDITS_PER_CREDIT,
            "stockpile": row["stockpile"],
            "budget": row["budget"] / _MILLICREDITS_PER_CREDIT,
        }
        for row in rows
    ]
    return pd.DataFrame(records)


@st.cache_data
def load_agent_summaries(episode_dir: str) -> pd.DataFrame:
    """Load per-agent summary stats from result.json as a DataFrame.

    Returns columns: agent_id, agent_type, net_worth, lifetime,
    total_trades, final_credits, cause_of_death.
    Credits are converted from millicredits to display credits.
    """
    path = Path(episode_dir) / "result.json"
    columns = [
        "agent_id",
        "agent_type",
        "net_worth",
        "lifetime",
        "total_trades",
        "final_credits",
        "cause_of_death",
    ]
    if not path.exists():
        return pd.DataFrame(columns=columns)

    result = json.loads(path.read_text())
    records = []
    for agent in result.get("agent_summaries", []):
        raw_type = agent.get("agent_type", "")
        short_type = (
            raw_type.removesuffix("Agent").lower()
            if raw_type.endswith("Agent")
            else raw_type.lower()
        )
        records.append(
            {
                "agent_id": agent["agent_id"],
                "agent_type": short_type,
                "net_worth": agent.get("final_net_worth", 0) / _MILLICREDITS_PER_CREDIT,
                "lifetime": agent.get("lifetime", 0),
                "total_trades": agent.get("total_trades", 0),
                "final_credits": agent.get("final_credits", 0)
                / _MILLICREDITS_PER_CREDIT,
                "cause_of_death": agent.get("cause_of_death"),
            }
        )
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(records)


@st.cache_data
def load_config(episode_dir: str) -> dict:
    """Load config.json from the episode directory."""
    path = Path(episode_dir) / "config.json"
    return json.loads(path.read_text())


@st.cache_data
def load_graph_topology(episode_dir: str) -> dict:
    """Reconstruct the world graph topology from config.json.

    Returns a dict with:
      - nodes: dict of node_id → {name, node_type, adjacent_nodes, resource_distribution, npc_buys}
      - edges: list of [node_a, node_b] pairs (deduplicated)
    """
    from evomarket.core.world import generate_world
    from evomarket.simulation.config import SimulationConfig

    config = load_config(episode_dir)
    seed = config.get("seed")
    if seed is None:
        raise ValueError(
            "config.json does not contain a 'seed' field; "
            "cannot reconstruct graph topology"
        )

    sim_config = SimulationConfig.from_json(config)
    world_config = sim_config.to_world_config()
    world = generate_world(world_config, seed)

    nodes: dict[str, dict] = {}
    seen_edges: set[tuple[str, str]] = set()
    edges: list[list[str]] = []

    for nid, node in world.nodes.items():
        # Determine primary resource from distribution
        dist = {k.value: v for k, v in node.resource_distribution.items()}
        primary_resource = max(dist, key=dist.get) if dist else None

        nodes[nid] = {
            "name": node.name,
            "node_type": node.node_type.value,
            "adjacent_nodes": list(node.adjacent_nodes),
            "resource_distribution": dist,
            "npc_buys": [c.value for c in node.npc_buys],
            "primary_resource": primary_resource,
        }

        for adj in node.adjacent_nodes:
            edge_key = tuple(sorted((nid, adj)))
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append(list(edge_key))

    return {"nodes": nodes, "edges": edges}


@st.cache_data
def load_result(episode_dir: str) -> dict:
    """Load result.json from the episode directory."""
    path = Path(episode_dir) / "result.json"
    return json.loads(path.read_text())


@st.cache_data
def load_agent_types(episode_dir: str) -> dict[str, str]:
    """Extract agent_id → agent_type mapping from result.json.

    Normalizes class names (e.g. "HarvesterAgent") to short names
    (e.g. "harvester") to match AGENT_TYPE_COLORS keys.
    """
    result = load_result(episode_dir)
    mapping: dict[str, str] = {}
    for agent in result.get("agent_summaries", []):
        raw = agent["agent_type"]
        # Normalize "HarvesterAgent" → "harvester", "RandomAgent" → "random", etc.
        short = (
            raw.removesuffix("Agent").lower() if raw.endswith("Agent") else raw.lower()
        )
        mapping[agent["agent_id"]] = short
    return mapping
