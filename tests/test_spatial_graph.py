"""Tests for the spatial graph visualization panel and data loading."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from evomarket.core.world import WorldConfig, generate_world


@pytest.fixture
def episode_dir(tmp_path: Path) -> Path:
    """Create a minimal episode directory with config.json and episode.sqlite."""
    config = WorldConfig()
    seed = 42
    world = generate_world(config, seed)

    # Write config.json matching expected format
    config_data = {
        "seed": seed,
        "world_config": config.model_dump(mode="json"),
    }
    (tmp_path / "config.json").write_text(json.dumps(config_data))

    # Create a minimal episode.sqlite with agent_snapshots
    db_path = tmp_path / "episode.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE agent_snapshots ("
        "  tick INTEGER, agent_id TEXT, credits INTEGER,"
        "  inventory_json TEXT, location TEXT, age INTEGER"
        ")"
    )

    # Insert snapshots for tick 0: agents at their spawn locations
    for aid, agent in world.agents.items():
        inv = {k.value: v for k, v in agent.inventory.items()}
        conn.execute(
            "INSERT INTO agent_snapshots VALUES (?, ?, ?, ?, ?, ?)",
            (0, aid, agent.credits, json.dumps(inv), agent.location, agent.age),
        )

    # Insert snapshots for tick 1: move some agents to different nodes
    node_ids = list(world.nodes.keys())
    for i, (aid, agent) in enumerate(world.agents.items()):
        new_loc = node_ids[i % len(node_ids)]
        inv = {k.value: v for k, v in agent.inventory.items()}
        conn.execute(
            "INSERT INTO agent_snapshots VALUES (?, ?, ?, ?, ?, ?)",
            (1, aid, agent.credits + i * 1000, json.dumps(inv), new_loc, 1),
        )

    conn.commit()
    conn.close()

    return tmp_path


class TestLoadGraphTopology:
    def test_returns_nodes_and_edges(self, episode_dir: Path) -> None:
        from visualization.data import load_graph_topology

        # Clear streamlit cache for testing
        load_graph_topology.clear()

        topo = load_graph_topology(str(episode_dir))

        assert "nodes" in topo
        assert "edges" in topo
        assert len(topo["nodes"]) > 0
        assert len(topo["edges"]) > 0

    def test_node_has_required_fields(self, episode_dir: Path) -> None:
        from visualization.data import load_graph_topology

        load_graph_topology.clear()
        topo = load_graph_topology(str(episode_dir))

        for nid, info in topo["nodes"].items():
            assert "name" in info
            assert "node_type" in info
            assert "adjacent_nodes" in info
            assert "resource_distribution" in info
            assert "npc_buys" in info
            assert info["node_type"] in ("RESOURCE", "TRADE_HUB", "SPAWN")

    def test_edges_reference_valid_nodes(self, episode_dir: Path) -> None:
        from visualization.data import load_graph_topology

        load_graph_topology.clear()
        topo = load_graph_topology(str(episode_dir))

        node_ids = set(topo["nodes"].keys())
        for a, b in topo["edges"]:
            assert a in node_ids, f"Edge references unknown node {a}"
            assert b in node_ids, f"Edge references unknown node {b}"

    def test_edges_are_deduplicated(self, episode_dir: Path) -> None:
        from visualization.data import load_graph_topology

        load_graph_topology.clear()
        topo = load_graph_topology(str(episode_dir))

        edge_set = {tuple(sorted(e)) for e in topo["edges"]}
        assert len(edge_set) == len(topo["edges"])

    def test_missing_seed_raises(self, tmp_path: Path) -> None:
        from visualization.data import load_graph_topology

        load_graph_topology.clear()

        config_data = {"world_config": WorldConfig().model_dump(mode="json")}
        (tmp_path / "config.json").write_text(json.dumps(config_data))

        with pytest.raises(ValueError, match="seed"):
            load_graph_topology(str(tmp_path))


class TestAgentJitter:
    def test_single_agent_no_jitter(self) -> None:
        """A single agent at a node should have no jitter offset."""
        from visualization.panels.spatial_graph import _agent_traces

        pos = {"node_a": (1.0, 2.0)}
        tick_agents = {
            "node_a": [
                {
                    "agent_id": "agent_001",
                    "credits": 30.0,
                    "inventory_IRON": 0,
                    "inventory_WOOD": 0,
                    "inventory_STONE": 0,
                    "inventory_HERBS": 0,
                    "age": 5,
                    "location": "node_a",
                }
            ]
        }
        traces = _agent_traces(pos, tick_agents)
        assert len(traces) == 1
        # Single agent: jitter_r is 0
        assert traces[0].x[0] == pytest.approx(1.0)
        assert traces[0].y[0] == pytest.approx(2.0)

    def test_multiple_agents_distinct_positions(self) -> None:
        """Multiple agents at the same node should have distinct positions."""
        from visualization.panels.spatial_graph import _agent_traces

        pos = {"node_a": (0.0, 0.0)}
        agents = [
            {
                "agent_id": f"agent_{i:03d}",
                "credits": 30.0,
                "inventory_IRON": 0,
                "inventory_WOOD": 0,
                "inventory_STONE": 0,
                "inventory_HERBS": 0,
                "age": 5,
                "location": "node_a",
            }
            for i in range(5)
        ]
        tick_agents = {"node_a": agents}
        traces = _agent_traces(pos, tick_agents)

        assert len(traces) == 1
        positions = list(zip(traces[0].x, traces[0].y))
        # All positions should be unique
        assert len(set(positions)) == len(positions)

    def test_jitter_is_deterministic(self) -> None:
        """Same input should produce same jitter positions."""
        from visualization.panels.spatial_graph import _agent_traces

        pos = {"node_a": (0.0, 0.0)}
        agents = [
            {
                "agent_id": f"agent_{i:03d}",
                "credits": 30.0,
                "inventory_IRON": 0,
                "inventory_WOOD": 0,
                "inventory_STONE": 0,
                "inventory_HERBS": 0,
                "age": 5,
                "location": "node_a",
            }
            for i in range(3)
        ]
        tick_agents = {"node_a": agents}

        traces1 = _agent_traces(pos, tick_agents)
        traces2 = _agent_traces(pos, tick_agents)

        assert list(traces1[0].x) == list(traces2[0].x)
        assert list(traces1[0].y) == list(traces2[0].y)


class TestAgentMarkerSizing:
    def test_wealthy_agent_larger_marker(self) -> None:
        """Agent with more credits should have a larger marker."""
        from visualization.panels.spatial_graph import _agent_traces

        pos = {"node_a": (0.0, 0.0), "node_b": (1.0, 1.0)}
        tick_agents = {
            "node_a": [
                {
                    "agent_id": "agent_rich",
                    "credits": 100.0,
                    "inventory_IRON": 0,
                    "inventory_WOOD": 0,
                    "inventory_STONE": 0,
                    "inventory_HERBS": 0,
                    "age": 5,
                    "location": "node_a",
                }
            ],
            "node_b": [
                {
                    "agent_id": "agent_poor",
                    "credits": 10.0,
                    "inventory_IRON": 0,
                    "inventory_WOOD": 0,
                    "inventory_STONE": 0,
                    "inventory_HERBS": 0,
                    "age": 5,
                    "location": "node_b",
                }
            ],
        }
        traces = _agent_traces(pos, tick_agents)
        sizes = traces[0].marker["size"]
        # Rich agent (first) should have larger marker than poor agent (second)
        assert sizes[0] > sizes[1]

    def test_zero_credits_has_minimum_size(self) -> None:
        """Agent with 0 credits should still have a visible marker."""
        from visualization.panels.spatial_graph import _agent_traces

        pos = {"node_a": (0.0, 0.0)}
        tick_agents = {
            "node_a": [
                {
                    "agent_id": "agent_broke",
                    "credits": 0.0,
                    "inventory_IRON": 0,
                    "inventory_WOOD": 0,
                    "inventory_STONE": 0,
                    "inventory_HERBS": 0,
                    "age": 5,
                    "location": "node_a",
                }
            ]
        }
        traces = _agent_traces(pos, tick_agents)
        assert traces[0].marker["size"][0] >= 6  # min_size


class TestHoverText:
    def test_agent_hover_contains_required_fields(self) -> None:
        from visualization.panels.spatial_graph import _agent_traces

        pos = {"node_a": (0.0, 0.0)}
        tick_agents = {
            "node_a": [
                {
                    "agent_id": "agent_001",
                    "credits": 30.0,
                    "inventory_IRON": 5,
                    "inventory_WOOD": 3,
                    "inventory_STONE": 0,
                    "inventory_HERBS": 2,
                    "age": 42,
                    "location": "node_a",
                }
            ]
        }
        traces = _agent_traces(pos, tick_agents)
        hover = traces[0].hovertext[0]

        assert "agent_001" in hover
        assert "30.00" in hover
        assert "Iron: 5" in hover
        assert "Wood: 3" in hover
        assert "42 ticks" in hover
        assert "node_a" in hover

    def test_node_hover_contains_required_fields(self) -> None:
        from visualization.panels.spatial_graph import _node_traces

        topo = {
            "nodes": {
                "node_test": {
                    "name": "Test Node",
                    "node_type": "RESOURCE",
                    "adjacent_nodes": [],
                    "resource_distribution": {"IRON": 0.7},
                    "npc_buys": ["IRON"],
                    "primary_resource": "IRON",
                }
            },
            "edges": [],
        }
        pos = {"node_test": (0.0, 0.0)}
        tick_agents = {
            "node_test": [
                {"agent_id": "agent_001", "credits": 30.0},
            ]
        }
        traces = _node_traces(topo, pos, tick_agents)
        hover = traces[0].hovertext[0]

        assert "Test Node" in hover
        assert "RESOURCE" in hover
        assert "Agents: 1" in hover
        assert "IRON" in hover
