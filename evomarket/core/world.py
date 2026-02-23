"""World graph, Node model, WorldConfig, and world generation."""

from __future__ import annotations

import random
from collections import deque

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from evomarket.core.agent import Agent
from evomarket.core.resources import validate_resource_distribution
from evomarket.core.types import CommodityType, Millicredits, NodeType


class Node(BaseModel):
    """A node in the world graph."""

    model_config = ConfigDict(frozen=False)

    node_id: str
    name: str
    node_type: NodeType
    resource_distribution: dict[CommodityType, float]
    resource_spawn_rate: float
    resource_stockpile: dict[CommodityType, float]
    resource_cap: int
    npc_buys: list[CommodityType]
    npc_base_prices: dict[CommodityType, Millicredits]
    npc_stockpile: dict[CommodityType, int]
    npc_stockpile_capacity: int
    npc_budget: Millicredits
    adjacent_nodes: list[str]

    @field_validator("resource_distribution")
    @classmethod
    def _validate_distribution(cls, v: dict[CommodityType, float]) -> dict[CommodityType, float]:
        return validate_resource_distribution(v)


class WorldConfig(BaseModel):
    """Configuration for world generation. Credit values are in millicredits."""

    model_config = ConfigDict(frozen=True)

    num_nodes: int = 15
    num_commodity_types: int = 4
    total_credit_supply: Millicredits = 10_000_000
    starting_credits: Millicredits = 30_000
    population_size: int = 20
    resource_spawn_rate: float = 0.5
    node_resource_cap: int = 20
    npc_base_price: Millicredits = 5_000
    npc_stockpile_capacity: int = 50
    npc_budget_replenish_rate: Millicredits = 5_000
    npc_stockpile_decay_rate: float = 0.1
    survival_tax: Millicredits = 1_000
    spawn_grace_period: int = 5
    ticks_per_episode: int = 500
    max_open_orders: int = 5
    max_pending_trades: int = 3
    death_treasury_return_pct: float = 0.5
    death_local_share_pct: float = 0.5

    @model_validator(mode="after")
    def _validate_config(self) -> WorldConfig:
        if self.num_commodity_types < 1 or self.num_commodity_types > len(CommodityType):
            raise ValueError(
                f"num_commodity_types must be between 1 and {len(CommodityType)}, "
                f"got {self.num_commodity_types}"
            )
        if self.population_size < 1:
            raise ValueError("population_size must be at least 1")
        if self.total_credit_supply < self.population_size * self.starting_credits:
            raise ValueError("total_credit_supply insufficient to fund starting agent credits")
        return self


def _get_commodity_types(config: WorldConfig) -> list[CommodityType]:
    """Return the commodity types in use based on config."""
    return list(CommodityType)[:config.num_commodity_types]


def _verify_connectivity(nodes: dict[str, Node]) -> None:
    """Assert the world graph is fully connected via BFS."""
    if not nodes:
        return
    start = next(iter(nodes))
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
    assert visited == set(nodes.keys()), (
        f"World graph is not connected. Reachable: {len(visited)}, Total: {len(nodes)}"
    )


def _add_edge(nodes: dict[str, Node], a: str, b: str) -> None:
    """Add a bidirectional edge between two nodes (idempotent)."""
    if b not in nodes[a].adjacent_nodes:
        nodes[a].adjacent_nodes.append(b)
    if a not in nodes[b].adjacent_nodes:
        nodes[b].adjacent_nodes.append(a)


def generate_world(config: WorldConfig, seed: int) -> WorldState:
    """Generate a deterministic world from config and seed.

    Topology strategy:
    1. Determine commodity types and create clusters (each cluster = 1 trade hub + 2-3 resource nodes)
    2. Create 1 spawn node connected to the first trade hub
    3. Build a spanning tree across all nodes for guaranteed connectivity
    4. Add intra-cluster edges
    """
    rng = random.Random(seed)
    commodities = _get_commodity_types(config)

    nodes: dict[str, Node] = {}
    cluster_membership: dict[str, int] = {}  # node_id -> cluster index

    # Distribute nodes: 1 spawn + clusters of (1 trade hub + N resource nodes)
    remaining = config.num_nodes - 1  # reserve 1 for spawn
    num_clusters = len(commodities)
    # Each cluster gets at least 1 trade hub + 2 resource nodes = 3 nodes
    # Distribute remaining nodes across clusters
    cluster_sizes: list[int] = []
    base_per_cluster = max(2, remaining // num_clusters)  # resource nodes per cluster
    for i in range(num_clusters):
        if i < num_clusters - 1:
            size = base_per_cluster
        else:
            # Last cluster gets the remainder (minus trade hubs)
            size = remaining - base_per_cluster * (num_clusters - 1)
        cluster_sizes.append(size)

    # Create spawn node
    spawn_node = Node(
        node_id="node_spawn",
        name="Spawn",
        node_type=NodeType.SPAWN,
        resource_distribution={},
        resource_spawn_rate=0.0,
        resource_stockpile={},
        resource_cap=0,
        npc_buys=[],
        npc_base_prices={},
        npc_stockpile={},
        npc_stockpile_capacity=0,
        npc_budget=0,
        adjacent_nodes=[],
    )
    nodes[spawn_node.node_id] = spawn_node

    trade_hub_ids: list[str] = []

    for ci, commodity in enumerate(commodities):
        # Create trade hub for this cluster
        hub_name = f"hub_{commodity.value.lower()}"
        hub_id = f"node_{hub_name}"
        hub = Node(
            node_id=hub_id,
            name=hub_name.replace("_", " ").title(),
            node_type=NodeType.TRADE_HUB,
            resource_distribution={},
            resource_spawn_rate=0.0,
            resource_stockpile={},
            resource_cap=0,
            npc_buys=list(commodities),  # trade hubs buy all commodities
            npc_base_prices={c: config.npc_base_price for c in commodities},
            npc_stockpile={c: 0 for c in commodities},
            npc_stockpile_capacity=config.npc_stockpile_capacity,
            npc_budget=0,  # will be allocated from treasury
            adjacent_nodes=[],
        )
        nodes[hub_id] = hub
        trade_hub_ids.append(hub_id)
        cluster_membership[hub_id] = ci

        # Create resource nodes for this cluster
        num_resource = cluster_sizes[ci]
        for ri in range(num_resource):
            rname = f"{commodity.value.lower()}_{ri}"
            rid = f"node_{rname}"

            # Primary commodity gets high weight, others get small weights
            dist: dict[CommodityType, float] = {}
            primary_weight = rng.uniform(0.5, 0.8)
            remaining_weight = 1.0 - primary_weight
            other_commodities = [c for c in commodities if c != commodity]
            if other_commodities:
                for oc in other_commodities:
                    w = rng.uniform(0, remaining_weight / len(other_commodities))
                    dist[oc] = round(w, 3)
                    remaining_weight -= w
            dist[commodity] = round(primary_weight, 3)

            resource_node = Node(
                node_id=rid,
                name=rname.replace("_", " ").title(),
                node_type=NodeType.RESOURCE,
                resource_distribution=dist,
                resource_spawn_rate=config.resource_spawn_rate,
                resource_stockpile={c: 0.0 for c in commodities},
                resource_cap=config.node_resource_cap,
                npc_buys=[commodity],  # resource nodes buy their native commodity
                npc_base_prices={commodity: config.npc_base_price},
                npc_stockpile={commodity: 0},
                npc_stockpile_capacity=config.npc_stockpile_capacity,
                npc_budget=0,
                adjacent_nodes=[],
            )
            nodes[rid] = resource_node
            cluster_membership[rid] = ci

            # Connect resource node to its cluster's trade hub
            _add_edge(nodes, rid, hub_id)

    # Connect spawn to first trade hub
    _add_edge(nodes, spawn_node.node_id, trade_hub_ids[0])

    # Build spanning tree across trade hubs (ensures global connectivity)
    rng.shuffle(trade_hub_ids)
    for i in range(1, len(trade_hub_ids)):
        # Connect each trade hub to a random previously-connected hub
        target = rng.choice(trade_hub_ids[:i])
        _add_edge(nodes, trade_hub_ids[i], target)

    # Add extra cross-cluster edges for richer topology
    all_node_ids = list(nodes.keys())
    num_extra_edges = max(1, len(all_node_ids) // 5)
    for _ in range(num_extra_edges):
        a = rng.choice(all_node_ids)
        b = rng.choice(all_node_ids)
        if a != b:
            _add_edge(nodes, a, b)

    # Verify connectivity
    _verify_connectivity(nodes)

    # Allocate NPC budgets from total supply
    npc_nodes = [n for n in nodes.values() if n.npc_buys]
    initial_budget_per_node = config.total_credit_supply // (10 * max(1, len(npc_nodes)))
    total_npc_budget = 0
    for node in npc_nodes:
        node.npc_budget = initial_budget_per_node
        total_npc_budget += initial_budget_per_node

    # Create agents at spawn nodes
    agents: dict[str, Agent] = {}
    spawn_nodes = [n for n in nodes.values() if n.node_type == NodeType.SPAWN]
    total_agent_credits = 0
    for i in range(config.population_size):
        agent_id = f"agent_{i:03d}"
        spawn_loc = rng.choice(spawn_nodes)
        agent = Agent(
            agent_id=agent_id,
            display_name=f"Agent {i}",
            location=spawn_loc.node_id,
            credits=config.starting_credits,
            inventory={c: 0 for c in commodities},
            age=0,
            alive=True,
            will={},
            prompt_document="",
            grace_ticks_remaining=config.spawn_grace_period,
        )
        agents[agent_id] = agent
        total_agent_credits += config.starting_credits

    # Treasury gets the remainder
    treasury = config.total_credit_supply - total_agent_credits - total_npc_budget

    assert treasury >= 0, (
        f"Insufficient total_credit_supply: agents need {total_agent_credits}, "
        f"NPC budgets need {total_npc_budget}, but total is {config.total_credit_supply}"
    )

    world = WorldState(
        nodes=nodes,
        agents=agents,
        treasury=treasury,
        total_supply=config.total_credit_supply,
        tick=0,
        next_agent_id=config.population_size,
        config=config,
        rng=rng,
    )
    world.verify_invariant()
    return world


# Import here to avoid circular import at module level; WorldState uses Node and Agent
# but generate_world is defined after both. We define WorldState below.


class WorldState:
    """Root container for the entire game state.

    Not a Pydantic model because it holds a random.Random instance.
    Provides controlled mutation via transfer_credits() and explicit JSON serialization.
    """

    def __init__(
        self,
        *,
        nodes: dict[str, Node],
        agents: dict[str, Agent],
        treasury: Millicredits,
        total_supply: Millicredits,
        tick: int,
        next_agent_id: int,
        config: WorldConfig,
        rng: random.Random,
        order_book: dict[str, object] | None = None,
        trade_proposals: dict[str, object] | None = None,
        trade_history: dict[str, list[object]] | None = None,
        next_order_seq: int = 0,
    ) -> None:
        self.nodes = nodes
        self.agents = agents
        self.treasury = treasury
        self.total_supply = total_supply
        self.tick = tick
        self.next_agent_id = next_agent_id
        self.config = config
        self.rng = rng
        # Trading state (typed as object to avoid circular import;
        # actual types are PostedOrder, TradeProposal, TradeResult)
        self.order_book: dict[str, object] = order_book if order_book is not None else {}
        self.trade_proposals: dict[str, object] = trade_proposals if trade_proposals is not None else {}
        self.trade_history: dict[str, list[object]] = trade_history if trade_history is not None else {}
        self.next_order_seq: int = next_order_seq

    def verify_invariant(self) -> None:
        """Assert the fixed-supply invariant: all credits sum to total_supply."""
        agent_credits = sum(a.credits for a in self.agents.values())
        npc_budgets = sum(n.npc_budget for n in self.nodes.values())
        actual = agent_credits + npc_budgets + self.treasury
        assert actual == self.total_supply, (
            f"Fixed-supply invariant violated: "
            f"agents={agent_credits} + npc_budgets={npc_budgets} + "
            f"treasury={self.treasury} = {actual} != {self.total_supply}"
        )

    def transfer_credits(self, from_id: str, to_id: str, amount: Millicredits) -> None:
        """Atomically transfer millicredits between reservoirs.

        Reservoir IDs: agent ID (e.g., 'agent_001'), node ID (e.g., 'node_iron_0')
        for NPC budget, or 'treasury'.

        Raises ValueError if source has insufficient funds.
        """
        if amount == 0:
            return
        if amount < 0:
            raise ValueError(f"Transfer amount must be non-negative, got {amount}")

        # Read source balance
        source_balance = self._get_balance(from_id)
        if source_balance < amount:
            raise ValueError(
                f"Insufficient funds in {from_id}: has {source_balance}, needs {amount}"
            )

        # Perform atomic transfer
        self._adjust_balance(from_id, -amount)
        self._adjust_balance(to_id, amount)

    def _get_balance(self, reservoir_id: str) -> Millicredits:
        """Get the current balance of a reservoir."""
        if reservoir_id == "treasury":
            return self.treasury
        if reservoir_id in self.agents:
            return self.agents[reservoir_id].credits
        if reservoir_id in self.nodes:
            return self.nodes[reservoir_id].npc_budget
        raise KeyError(f"Unknown reservoir: {reservoir_id}")

    def _adjust_balance(self, reservoir_id: str, delta: Millicredits) -> None:
        """Adjust a reservoir's balance by delta."""
        if reservoir_id == "treasury":
            self.treasury += delta
        elif reservoir_id in self.agents:
            self.agents[reservoir_id].credits += delta
        elif reservoir_id in self.nodes:
            self.nodes[reservoir_id].npc_budget += delta
        else:
            raise KeyError(f"Unknown reservoir: {reservoir_id}")

    def get_npc_price(self, node_id: str, commodity: CommodityType) -> Millicredits:
        """Get the current NPC buy price for a commodity at a node.

        Uses supply-responsive pricing: base_price * (capacity - stockpile) // capacity
        Returns 0 if the commodity is not bought at this node.
        """
        node = self.nodes[node_id]
        if commodity not in node.npc_buys:
            return 0
        base_price = node.npc_base_prices.get(commodity, 0)
        stockpile = node.npc_stockpile.get(commodity, 0)
        capacity = node.npc_stockpile_capacity
        if capacity == 0:
            return 0
        return base_price * (capacity - stockpile) // capacity

    def orders_at_node(self, node_id: str) -> list[object]:
        """Return all active orders at the given node."""
        from evomarket.engine.trading import OrderStatus

        return [
            o
            for o in self.order_book.values()
            if getattr(o, "node_id", None) == node_id
            and getattr(o, "status", None) == OrderStatus.ACTIVE
        ]

    def orders_for_agent(self, agent_id: str) -> list[object]:
        """Return all non-terminal orders for the given agent."""
        from evomarket.engine.trading import OrderStatus

        return [
            o
            for o in self.order_book.values()
            if getattr(o, "poster_id", None) == agent_id
            and getattr(o, "status", None)
            in (OrderStatus.ACTIVE, OrderStatus.SUSPENDED)
        ]

    def pending_proposals_for_agent(self, agent_id: str) -> list[object]:
        """Return all pending trade proposals where agent is proposer."""
        from evomarket.engine.trading import TradeStatus

        return [
            p
            for p in self.trade_proposals.values()
            if getattr(p, "proposer_id", None) == agent_id
            and getattr(p, "status", None) == TradeStatus.PENDING
        ]

    def agents_at_node(self, node_id: str) -> list[Agent]:
        """Return all living agents at the given node."""
        return [a for a in self.agents.values() if a.alive and a.location == node_id]

    def adjacent_nodes(self, node_id: str) -> list[str]:
        """Return the list of node IDs adjacent to the given node."""
        return list(self.nodes[node_id].adjacent_nodes)

    def to_json(self) -> dict:
        """Serialize the entire world state to a JSON-compatible dict."""
        from evomarket.engine.trading import PostedOrder, TradeProposal, TradeResult

        def _serialize_trade_result(r: object) -> dict:
            assert isinstance(r, TradeResult)
            return {
                "success": r.success,
                "trade_type": r.trade_type,
                "buyer_id": r.buyer_id,
                "seller_id": r.seller_id,
                "items_transferred": {k.value: v for k, v in r.items_transferred.items()},
                "credits_transferred": r.credits_transferred,
                "failure_reason": r.failure_reason,
                "tick": r.tick,
            }

        order_book_json = {}
        for oid, o in self.order_book.items():
            assert isinstance(o, PostedOrder)
            order_book_json[oid] = o.model_dump(mode="json")

        proposals_json = {}
        for tid, p in self.trade_proposals.items():
            assert isinstance(p, TradeProposal)
            proposals_json[tid] = p.model_dump(mode="json")

        history_json: dict[str, list[dict]] = {}
        for node_id, results in self.trade_history.items():
            history_json[node_id] = [_serialize_trade_result(r) for r in results]

        return {
            "nodes": {nid: n.model_dump(mode="json") for nid, n in self.nodes.items()},
            "agents": {aid: a.model_dump(mode="json") for aid, a in self.agents.items()},
            "treasury": self.treasury,
            "total_supply": self.total_supply,
            "tick": self.tick,
            "next_agent_id": self.next_agent_id,
            "config": self.config.model_dump(mode="json"),
            "rng_state": self.rng.getstate(),
            "order_book": order_book_json,
            "trade_proposals": proposals_json,
            "trade_history": history_json,
            "next_order_seq": self.next_order_seq,
        }

    @classmethod
    def from_json(cls, data: dict) -> WorldState:
        """Deserialize a world state from a JSON-compatible dict."""
        from evomarket.engine.trading import (
            CommodityType as CT,
            PostedOrder,
            TradeProposal,
            TradeResult,
        )

        nodes = {nid: Node.model_validate(ndata) for nid, ndata in data["nodes"].items()}
        agents = {aid: Agent.model_validate(adata) for aid, adata in data["agents"].items()}
        config = WorldConfig.model_validate(data["config"])
        rng = random.Random()
        rng.setstate(data["rng_state"])

        # Deserialize trading state
        order_book: dict[str, object] = {}
        for oid, odata in data.get("order_book", {}).items():
            order_book[oid] = PostedOrder.model_validate(odata)

        trade_proposals: dict[str, object] = {}
        for tid, pdata in data.get("trade_proposals", {}).items():
            trade_proposals[tid] = TradeProposal.model_validate(pdata)

        trade_history: dict[str, list[object]] = {}
        for node_id, results in data.get("trade_history", {}).items():
            trade_history[node_id] = [
                TradeResult(
                    success=r["success"],
                    trade_type=r["trade_type"],
                    buyer_id=r["buyer_id"],
                    seller_id=r["seller_id"],
                    items_transferred={CT(k): v for k, v in r["items_transferred"].items()},
                    credits_transferred=r["credits_transferred"],
                    failure_reason=r["failure_reason"],
                    tick=r["tick"],
                )
                for r in results
            ]

        return cls(
            nodes=nodes,
            agents=agents,
            treasury=data["treasury"],
            total_supply=data["total_supply"],
            tick=data["tick"],
            next_agent_id=data["next_agent_id"],
            config=config,
            rng=rng,
            order_book=order_book,
            trade_proposals=trade_proposals,
            trade_history=trade_history,
            next_order_seq=data.get("next_order_seq", 0),
        )
