"""Tests for observation generation."""

from evomarket.core.types import NodeType
from evomarket.core.world import WorldConfig, generate_world, WorldState
from evomarket.engine.communication import (
    SendMessageAction,
    send_message,
    deliver_pending_messages,
)
from evomarket.engine.observation import (
    generate_observations,
)
from evomarket.engine.trading import BuySell, post_order, propose_trade


def _make_world() -> WorldState:
    config = WorldConfig(
        num_nodes=5,
        num_commodity_types=2,
        population_size=5,
        total_credit_supply=10_000_000,
        starting_credits=30_000,
    )
    return generate_world(config, seed=42)


class TestObservationGeneration:
    """Tests for generate_observations."""

    def test_returns_observations_for_living_agents(self) -> None:
        world = _make_world()
        obs = generate_observations(world)
        alive = [a for a in world.agents.values() if a.alive]
        assert len(obs) == len(alive)
        for agent_id in obs:
            assert world.agents[agent_id].alive

    def test_dead_agents_excluded(self) -> None:
        world = _make_world()
        first_id = next(iter(world.agents))
        world.agents[first_id].alive = False
        obs = generate_observations(world)
        assert first_id not in obs

    def test_agent_state_view(self) -> None:
        world = _make_world()
        first_id = next(iter(world.agents))
        agent = world.agents[first_id]
        obs = generate_observations(world)
        state = obs[first_id].agent_state
        assert state.location == agent.location
        assert state.credits == agent.credits
        assert state.age == agent.age
        assert state.grace_ticks_remaining == agent.grace_ticks_remaining

    def test_node_info(self) -> None:
        world = _make_world()
        first_id = next(iter(world.agents))
        agent = world.agents[first_id]
        obs = generate_observations(world)
        node_info = obs[first_id].node_info
        node = world.nodes[agent.location]
        assert node_info.node_id == node.node_id
        assert node_info.name == node.name
        assert node_info.node_type == node.node_type.value
        assert set(node_info.adjacent_nodes) == set(node.adjacent_nodes)

    def test_node_info_npc_prices(self) -> None:
        world = _make_world()
        # Move an agent to a trade hub that has NPC buys
        trade_hub_id = None
        for nid, node in world.nodes.items():
            if node.npc_buys:
                trade_hub_id = nid
                break
        assert trade_hub_id is not None

        first_id = next(iter(world.agents))
        world.agents[first_id].location = trade_hub_id
        obs = generate_observations(world)
        npc_prices = obs[first_id].node_info.npc_prices
        node = world.nodes[trade_hub_id]
        for commodity in node.npc_buys:
            assert commodity in npc_prices

    def test_resource_availability(self) -> None:
        world = _make_world()
        # Find a resource node and set a stockpile
        resource_node_id = None
        for nid, node in world.nodes.items():
            if node.node_type == NodeType.RESOURCE:
                resource_node_id = nid
                break
        assert resource_node_id is not None

        node = world.nodes[resource_node_id]
        commodity = list(node.resource_stockpile.keys())[0]
        node.resource_stockpile[commodity] = 3.7

        first_id = next(iter(world.agents))
        world.agents[first_id].location = resource_node_id
        obs = generate_observations(world)
        avail = obs[first_id].node_info.resource_availability
        assert avail[commodity] == 3  # floor(3.7) = 3

    def test_agents_present_excludes_self(self) -> None:
        world = _make_world()
        # Put two agents at same node
        ids = list(world.agents.keys())
        node_id = world.agents[ids[0]].location
        world.agents[ids[1]].location = node_id
        obs = generate_observations(world)
        present_ids = [a.agent_id for a in obs[ids[0]].agents_present]
        assert ids[0] not in present_ids
        assert ids[1] in present_ids

    def test_posted_orders(self) -> None:
        world = _make_world()
        first_id = next(iter(world.agents))
        agent = world.agents[first_id]
        commodity = list(agent.inventory.keys())[0]
        agent.inventory[commodity] = 5

        order = post_order(
            world,
            first_id,
            side=BuySell.SELL,
            commodity=commodity,
            quantity=2,
            price_per_unit=1000,
        )
        assert order is not None

        obs = generate_observations(world)
        order_ids = [o.order_id for o in obs[first_id].posted_orders]
        assert order.order_id in order_ids

    def test_messages_received(self) -> None:
        world = _make_world()
        ids = list(world.agents.keys())
        # Put agents together
        node_id = world.agents[ids[0]].location
        world.agents[ids[1]].location = node_id

        action = SendMessageAction(sender_id=ids[0], recipient=ids[1], text="hello")
        send_message(world, action)
        deliver_pending_messages(world)

        obs = generate_observations(world)
        msgs = obs[ids[1]].messages_received
        assert len(msgs) >= 1
        assert msgs[0].text == "hello"

    def test_pending_proposals(self) -> None:
        world = _make_world()
        ids = list(world.agents.keys())
        node_id = world.agents[ids[0]].location
        world.agents[ids[1]].location = node_id

        commodity = list(world.agents[ids[0]].inventory.keys())[0]
        world.agents[ids[0]].inventory[commodity] = 5

        proposal = propose_trade(
            world,
            ids[0],
            ids[1],
            offer_commodities={commodity: 1},
        )
        assert proposal is not None

        obs = generate_observations(world)
        # Target sees it in pending_proposals
        prop_ids = [p.trade_id for p in obs[ids[1]].pending_proposals]
        assert proposal.trade_id in prop_ids

    def test_own_orders(self) -> None:
        world = _make_world()
        first_id = next(iter(world.agents))
        agent = world.agents[first_id]
        commodity = list(agent.inventory.keys())[0]
        agent.inventory[commodity] = 5

        order = post_order(
            world,
            first_id,
            side=BuySell.SELL,
            commodity=commodity,
            quantity=2,
            price_per_unit=1000,
        )
        assert order is not None

        obs = generate_observations(world)
        own_order_ids = [o.order_id for o in obs[first_id].own_orders]
        assert order.order_id in own_order_ids

    def test_own_will(self) -> None:
        world = _make_world()
        ids = list(world.agents.keys())
        world.agents[ids[0]].will = {ids[1]: 0.5}
        obs = generate_observations(world)
        assert obs[ids[0]].own_will == {ids[1]: 0.5}

    def test_preamble_tick(self) -> None:
        world = _make_world()
        world.tick = 42
        obs = generate_observations(world)
        for observation in obs.values():
            assert observation.preamble.tick == 42

    def test_prompt_document(self) -> None:
        world = _make_world()
        first_id = next(iter(world.agents))
        world.agents[first_id].prompt_document = "my notes"
        obs = generate_observations(world)
        assert obs[first_id].prompt_document == "my notes"
