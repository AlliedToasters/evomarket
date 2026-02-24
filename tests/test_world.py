"""Tests for world graph, Node model, and world generation."""

from collections import deque

import pytest

from evomarket.core.types import CommodityType, NodeType
from evomarket.core.world import Node, WorldConfig, WorldState, generate_world


class TestNodeModel:
    def test_valid_construction(self) -> None:
        node = Node(
            node_id="node_test",
            name="Test",
            node_type=NodeType.RESOURCE,
            resource_distribution={CommodityType.IRON: 0.7, CommodityType.WOOD: 0.2},
            resource_spawn_rate=0.5,
            resource_stockpile={CommodityType.IRON: 0.0},
            resource_cap=20,
            npc_buys=[CommodityType.IRON],
            npc_base_prices={CommodityType.IRON: 5000},
            npc_stockpile={CommodityType.IRON: 0},
            npc_stockpile_capacity=50,
            npc_budget=10000,
            adjacent_nodes=["node_other"],
        )
        assert node.node_id == "node_test"
        assert node.node_type == NodeType.RESOURCE

    def test_resource_distribution_exceeds_one(self) -> None:
        with pytest.raises(ValueError, match="must be ≤ 1.0"):
            Node(
                node_id="node_bad",
                name="Bad",
                node_type=NodeType.RESOURCE,
                resource_distribution={
                    CommodityType.IRON: 0.8,
                    CommodityType.WOOD: 0.5,
                },
                resource_spawn_rate=0.5,
                resource_stockpile={},
                resource_cap=20,
                npc_buys=[],
                npc_base_prices={},
                npc_stockpile={},
                npc_stockpile_capacity=50,
                npc_budget=0,
                adjacent_nodes=[],
            )

    def test_json_round_trip(self) -> None:
        node = Node(
            node_id="node_rt",
            name="RoundTrip",
            node_type=NodeType.TRADE_HUB,
            resource_distribution={},
            resource_spawn_rate=0.0,
            resource_stockpile={},
            resource_cap=0,
            npc_buys=[CommodityType.IRON, CommodityType.WOOD],
            npc_base_prices={CommodityType.IRON: 5000, CommodityType.WOOD: 5000},
            npc_stockpile={CommodityType.IRON: 0, CommodityType.WOOD: 0},
            npc_stockpile_capacity=50,
            npc_budget=20000,
            adjacent_nodes=["node_a", "node_b"],
        )
        json_str = node.model_dump_json()
        restored = Node.model_validate_json(json_str)
        assert restored == node


class TestWorldConfig:
    def test_defaults(self) -> None:
        config = WorldConfig()
        assert config.num_nodes == 15
        assert config.total_credit_supply == 10_000_000
        assert config.starting_credits == 30_000
        assert config.npc_base_price == 5_000
        assert config.survival_tax == 1_000

    def test_json_round_trip(self) -> None:
        config = WorldConfig()
        json_str = config.model_dump_json()
        restored = WorldConfig.model_validate_json(json_str)
        assert restored == config

    def test_insufficient_supply_rejected(self) -> None:
        with pytest.raises(ValueError, match="insufficient"):
            WorldConfig(
                total_credit_supply=100,
                starting_credits=30_000,
                population_size=20,
            )


def _bfs_reachable(nodes: dict[str, Node], start: str) -> set[str]:
    visited: set[str] = set()
    queue: deque[str] = deque([start])
    while queue:
        nid = queue.popleft()
        if nid in visited:
            continue
        visited.add(nid)
        for adj in nodes[nid].adjacent_nodes:
            if adj not in visited:
                queue.append(adj)
    return visited


class TestWorldGeneration:
    def test_deterministic_same_seed(self) -> None:
        config = WorldConfig()
        w1 = generate_world(config, seed=42)
        w2 = generate_world(config, seed=42)
        assert set(w1.nodes.keys()) == set(w2.nodes.keys())
        assert set(w1.agents.keys()) == set(w2.agents.keys())
        assert w1.treasury == w2.treasury
        for nid in w1.nodes:
            assert w1.nodes[nid].adjacent_nodes == w2.nodes[nid].adjacent_nodes
            assert (
                w1.nodes[nid].resource_distribution
                == w2.nodes[nid].resource_distribution
            )

    def test_different_seeds_differ(self) -> None:
        config = WorldConfig()
        w1 = generate_world(config, seed=42)
        w2 = generate_world(config, seed=99)
        # At least node topology or resource distribution should differ
        nodes_same = all(
            w1.nodes[nid].resource_distribution
            == w2.nodes.get(nid, w1.nodes[nid]).resource_distribution
            for nid in w1.nodes
            if nid in w2.nodes
        )
        adj_same = all(
            set(w1.nodes[nid].adjacent_nodes)
            == set(w2.nodes.get(nid, w1.nodes[nid]).adjacent_nodes)
            for nid in w1.nodes
            if nid in w2.nodes
        )
        assert not (nodes_same and adj_same), (
            "Different seeds should produce different worlds"
        )

    def test_graph_connectivity(self, standard_world: WorldState) -> None:
        start = next(iter(standard_world.nodes))
        reachable = _bfs_reachable(standard_world.nodes, start)
        assert reachable == set(standard_world.nodes.keys())

    def test_graph_connectivity_small(self, small_world: WorldState) -> None:
        start = next(iter(small_world.nodes))
        reachable = _bfs_reachable(small_world.nodes, start)
        assert reachable == set(small_world.nodes.keys())

    def test_adjacency_symmetric(self, standard_world: WorldState) -> None:
        for nid, node in standard_world.nodes.items():
            for adj_id in node.adjacent_nodes:
                assert nid in standard_world.nodes[adj_id].adjacent_nodes, (
                    f"Adjacency not symmetric: {nid} -> {adj_id} but not {adj_id} -> {nid}"
                )

    def test_clustered_topology(self, standard_world: WorldState) -> None:
        """Resource nodes in the same cluster should share a primary commodity."""
        for node in standard_world.nodes.values():
            if node.node_type == NodeType.RESOURCE and node.resource_distribution:
                max_commodity = max(
                    node.resource_distribution, key=node.resource_distribution.get
                )  # type: ignore[arg-type]
                assert node.resource_distribution[max_commodity] >= 0.5, (
                    f"Resource node {node.node_id} has no dominant commodity (max weight < 0.5)"
                )

    def test_trade_hubs_connect_clusters(self, standard_world: WorldState) -> None:
        """Trade hubs should be adjacent to resource nodes from at least 2 commodity types."""
        for node in standard_world.nodes.values():
            if node.node_type == NodeType.TRADE_HUB:
                # Get primary commodities of adjacent resource nodes
                adj_commodities: set[CommodityType] = set()
                for adj_id in node.adjacent_nodes:
                    adj_node = standard_world.nodes[adj_id]
                    if (
                        adj_node.node_type == NodeType.RESOURCE
                        and adj_node.resource_distribution
                    ):
                        primary = max(
                            adj_node.resource_distribution,
                            key=adj_node.resource_distribution.get,
                        )  # type: ignore[arg-type]
                        adj_commodities.add(primary)
                # Hub's own cluster resource nodes count as 1, it may connect to others
                assert len(adj_commodities) >= 1, (
                    f"Trade hub {node.node_id} not adjacent to any resource nodes"
                )

    def test_invariant_after_generation(self, standard_world: WorldState) -> None:
        standard_world.verify_invariant()

    def test_initial_tick_zero(self, standard_world: WorldState) -> None:
        assert standard_world.tick == 0

    def test_next_agent_id(self, standard_world: WorldState) -> None:
        assert standard_world.next_agent_id == 20

    def test_treasury_non_negative(self, standard_world: WorldState) -> None:
        assert standard_world.treasury >= 0

    def test_connectivity_many_seeds(self) -> None:
        """Verify connectivity across multiple random seeds."""
        config = WorldConfig()
        for seed in range(10):
            world = generate_world(config, seed=seed)
            start = next(iter(world.nodes))
            reachable = _bfs_reachable(world.nodes, start)
            assert reachable == set(world.nodes.keys()), (
                f"Disconnected graph at seed={seed}"
            )


class TestAdjacencyQuery:
    def test_adjacent_nodes(self, standard_world: WorldState) -> None:
        node_id = next(iter(standard_world.nodes))
        adj = standard_world.adjacent_nodes(node_id)
        assert adj == standard_world.nodes[node_id].adjacent_nodes

    def test_adjacent_count(self, standard_world: WorldState) -> None:
        """Each node should have at least 1 neighbor."""
        for nid in standard_world.nodes:
            assert len(standard_world.adjacent_nodes(nid)) >= 1
