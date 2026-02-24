"""Spatial graph visualization panel — world topology with agents over time."""

from __future__ import annotations

import math
from pathlib import Path

import networkx as nx
import plotly.graph_objects as go
import streamlit as st

from visualization import data
from visualization.registry import register_panel
from visualization.common import NODE_TYPE_COLORS, format_credits

# ---------------------------------------------------------------------------
# Graph layout (cached — topology is static for an episode)
# ---------------------------------------------------------------------------

_MILLICREDITS_PER_CREDIT = 1000


@st.cache_data
def _compute_layout(
    episode_dir: str,
) -> tuple[dict, dict[str, tuple[float, float]]]:
    """Build a NetworkX graph and compute spring layout positions.

    Returns (topology_dict, positions) where positions maps node_id → (x, y).
    """
    topo = data.load_graph_topology(episode_dir)

    G = nx.Graph()
    for nid in topo["nodes"]:
        G.add_node(nid)
    for edge in topo["edges"]:
        G.add_edge(edge[0], edge[1])

    pos = nx.spring_layout(G, seed=42, k=2.0 / math.sqrt(max(len(G), 1)))
    return topo, {nid: (xy[0], xy[1]) for nid, xy in pos.items()}


# ---------------------------------------------------------------------------
# Trace builders
# ---------------------------------------------------------------------------


def _edge_traces(topo: dict, pos: dict[str, tuple[float, float]]) -> list[go.Scatter]:
    """Create line traces for graph edges."""
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []

    for a, b in topo["edges"]:
        x0, y0 = pos[a]
        x1, y1 = pos[b]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    return [
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line={"width": 1, "color": "#CCCCCC"},
            hoverinfo="skip",
            showlegend=False,
        )
    ]


def _node_traces(
    topo: dict,
    pos: dict[str, tuple[float, float]],
    tick_agents: dict[str, list[dict]],
) -> list[go.Scatter]:
    """Create one scatter trace per NodeType, colored by NODE_TYPE_COLORS."""
    # Group nodes by type
    by_type: dict[str, list[str]] = {}
    for nid, info in topo["nodes"].items():
        by_type.setdefault(info["node_type"], []).append(nid)

    traces: list[go.Scatter] = []
    for node_type, nids in by_type.items():
        xs = [pos[nid][0] for nid in nids]
        ys = [pos[nid][1] for nid in nids]

        hover_texts: list[str] = []
        labels: list[str] = []
        for nid in nids:
            info = topo["nodes"][nid]
            labels.append(info["name"])

            agents_here = tick_agents.get(nid, [])
            agent_count = len(agents_here)
            total_wealth = sum(a["credits"] for a in agents_here)

            lines = [
                f"<b>{info['name']}</b>",
                f"Type: {info['node_type']}",
                f"Agents: {agent_count}",
                f"Total wealth: {format_credits(int(total_wealth * _MILLICREDITS_PER_CREDIT))}",
            ]
            if info["primary_resource"]:
                lines.append(f"Primary resource: {info['primary_resource']}")
            if info["npc_buys"]:
                lines.append(f"NPC buys: {', '.join(info['npc_buys'])}")
            hover_texts.append("<br>".join(lines))

        color = NODE_TYPE_COLORS.get(node_type, "#999999")
        traces.append(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers+text",
                marker={
                    "size": 20,
                    "color": color,
                    "line": {"width": 1, "color": "#333"},
                },
                text=labels,
                textposition="top center",
                textfont={"size": 9},
                hovertext=hover_texts,
                hoverinfo="text",
                name=node_type,
                legendgroup="nodes",
            )
        )
    return traces


def _agent_traces(
    pos: dict[str, tuple[float, float]],
    tick_agents: dict[str, list[dict]],
) -> list[go.Scatter]:
    """Create a scatter trace for agents, sized by wealth, with jitter."""
    if not tick_agents:
        return []

    xs: list[float] = []
    ys: list[float] = []
    sizes: list[float] = []
    hover_texts: list[str] = []

    # Collect all credits for scaling
    all_credits = [a["credits"] for agents in tick_agents.values() for a in agents]
    if not all_credits:
        return []

    max_credits = max(all_credits) if all_credits else 1.0
    min_size, max_size = 6, 24

    for nid, agents in tick_agents.items():
        if nid not in pos:
            continue
        cx, cy = pos[nid]

        for i, agent in enumerate(agents):
            # Deterministic jitter based on agent index
            angle = 2 * math.pi * i / max(len(agents), 1)
            jitter_r = 0.03 if len(agents) > 1 else 0.0
            ax = cx + jitter_r * math.cos(angle)
            ay = cy + jitter_r * math.sin(angle)

            xs.append(ax)
            ys.append(ay)

            # Size proportional to credits
            if max_credits > 0:
                frac = agent["credits"] / max_credits
            else:
                frac = 0.0
            sizes.append(min_size + frac * (max_size - min_size))

            lines = [
                f"<b>{agent['agent_id']}</b>",
                f"Credits: {format_credits(int(agent['credits'] * _MILLICREDITS_PER_CREDIT))}",
                f"Iron: {agent['inventory_IRON']}  Wood: {agent['inventory_WOOD']}",
                f"Stone: {agent['inventory_STONE']}  Herbs: {agent['inventory_HERBS']}",
                f"Age: {agent['age']} ticks",
                f"Location: {agent['location']}",
            ]
            hover_texts.append("<br>".join(lines))

    return [
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers",
            marker={
                "size": sizes,
                "color": "#E91E63",
                "opacity": 0.8,
                "line": {"width": 0.5, "color": "#880E4F"},
            },
            hovertext=hover_texts,
            hoverinfo="text",
            name="Agents (size = wealth)",
            legendgroup="agents",
        )
    ]


# ---------------------------------------------------------------------------
# Panel render function
# ---------------------------------------------------------------------------


def render_spatial_graph(episode_dir: str) -> None:
    """Render the spatial graph panel."""
    st.header("Spatial Graph")

    db_path = str(Path(episode_dir) / "episode.sqlite")

    # Load data
    try:
        topo, pos = _compute_layout(episode_dir)
    except (ValueError, FileNotFoundError) as e:
        st.error(f"Cannot load graph topology: {e}")
        return

    snapshots = data.load_agent_snapshots(db_path)
    if snapshots.empty:
        st.warning("No agent snapshot data available.")
        return

    max_tick = int(snapshots["tick"].max())

    # Playback controls
    col_play, col_speed = st.columns([1, 1])
    with col_play:
        playing = st.toggle("Play", key="spatial_play")
    with col_speed:
        step_size = st.selectbox(
            "Step size", options=[1, 5, 10, 25], index=0, key="spatial_step"
        )

    # Auto-advance: update session state *before* slider is created
    if playing:
        import time

        current = st.session_state.get("spatial_tick", 0)
        if current < max_tick:
            st.session_state["spatial_tick"] = min(current + step_size, max_tick)
        else:
            st.session_state["spatial_play"] = False

    # Tick slider
    selected_tick = st.slider(
        "Tick",
        min_value=0,
        max_value=max_tick,
        value=0,
        key="spatial_tick",
    )

    # Filter snapshots for selected tick and group by location
    tick_df = snapshots[snapshots["tick"] == selected_tick]
    tick_agents: dict[str, list[dict]] = {}
    for _, row in tick_df.iterrows():
        loc = row["location"]
        tick_agents.setdefault(loc, []).append(row.to_dict())

    # Build figure
    fig = go.Figure()

    for trace in _edge_traces(topo, pos):
        fig.add_trace(trace)
    for trace in _node_traces(topo, pos, tick_agents):
        fig.add_trace(trace)
    for trace in _agent_traces(pos, tick_agents):
        fig.add_trace(trace)

    fig.update_layout(
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        xaxis={"visible": False},
        yaxis={"visible": False, "scaleanchor": "x"},
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
        height=700,
        hovermode="closest",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Summary metrics below the graph
    agent_count = len(tick_df)
    total_wealth = tick_df["credits"].sum() if not tick_df.empty else 0
    st.caption(
        f"Tick {selected_tick} · {agent_count} agents alive · "
        f"Total wealth: {format_credits(int(total_wealth * _MILLICREDITS_PER_CREDIT))}"
    )

    # Schedule rerun for next frame (after chart is rendered)
    if playing and selected_tick < max_tick:
        import time

        time.sleep(0.15)
        st.rerun()


# ---------------------------------------------------------------------------
# Register with app shell
# ---------------------------------------------------------------------------

register_panel("Spatial Graph", render_spatial_graph)
