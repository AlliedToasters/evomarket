"""NPC Prices heatmap panel — price dynamics across nodes and time."""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from visualization import data
from visualization.app import register_panel
from visualization.common import COMMODITY_COLORS, tick_range_selector


def _make_heatmap(
    df_commodity, commodity: str, start_tick: int, end_tick: int
) -> go.Figure:
    """Build a Plotly heatmap for a single commodity."""
    filtered = df_commodity[
        (df_commodity["tick"] >= start_tick) & (df_commodity["tick"] <= end_tick)
    ]

    if filtered.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data in selected range", showarrow=False)
        return fig

    pivot = filtered.pivot(index="node_id", columns="tick", values="price").fillna(0)
    nodes = list(pivot.index)
    ticks = list(pivot.columns)
    z = pivot.values.tolist()

    base_color = COMMODITY_COLORS.get(commodity, "#888888")

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=ticks,
            y=nodes,
            colorscale=[[0, "white"], [1, base_color]],
            hovertemplate=(
                "Node: %{y}<br>Tick: %{x}<br>Price: %{z:.2f}<extra></extra>"
            ),
            colorbar=dict(title="Price"),
        )
    )
    fig.update_layout(
        xaxis_title="Tick",
        yaxis_title="Node",
        height=max(300, len(nodes) * 30 + 100),
        margin=dict(l=0, r=0, t=30, b=0),
    )
    return fig


def _make_price_curves(
    df, node_id: str, start_tick: int, end_tick: int
) -> go.Figure:
    """Build a line chart of price vs tick for all commodities at a node."""
    node_df = df[
        (df["node_id"] == node_id)
        & (df["tick"] >= start_tick)
        & (df["tick"] <= end_tick)
    ]

    fig = go.Figure()
    for commodity in sorted(node_df["commodity"].unique()):
        cdf = node_df[node_df["commodity"] == commodity].sort_values("tick")
        fig.add_trace(
            go.Scatter(
                x=cdf["tick"],
                y=cdf["price"],
                mode="lines",
                name=commodity,
                line=dict(color=COMMODITY_COLORS.get(commodity, "#888888")),
            )
        )

    fig.update_layout(
        xaxis_title="Tick",
        yaxis_title="Price (credits)",
        height=350,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def render(episode_dir: str) -> None:
    """Render the NPC Prices panel."""
    st.title("NPC Prices")

    db_path = str(Path(episode_dir) / "episode.sqlite")

    if not data.has_npc_snapshots(db_path):
        st.info(
            "NPC price data is not available for this episode. "
            "Re-run the simulation with a newer version to generate NPC snapshots."
        )
        return

    df = data.load_npc_snapshots(db_path)
    if df.empty:
        st.warning("NPC snapshot table exists but contains no data.")
        return

    max_tick = int(df["tick"].max())
    commodities = sorted(df["commodity"].unique())
    all_nodes = sorted(df["node_id"].unique())

    # Controls
    start_tick, end_tick = tick_range_selector(max_tick, key="npc_prices_tick")

    # Node selector for price curves
    selected_node = st.selectbox(
        "Select node for price curves",
        options=[""] + all_nodes,
        format_func=lambda x: "(none)" if x == "" else x,
        key="npc_prices_node",
    )

    # Price curves for selected node
    if selected_node:
        st.subheader(f"Price Curves — {selected_node}")
        fig_curves = _make_price_curves(df, selected_node, start_tick, end_tick)
        st.plotly_chart(fig_curves, use_container_width=True)

    # Commodity heatmap tabs
    tabs = st.tabs(commodities)
    for tab, commodity in zip(tabs, commodities):
        with tab:
            df_c = df[df["commodity"] == commodity]
            fig = _make_heatmap(df_c, commodity, start_tick, end_tick)
            st.plotly_chart(fig, use_container_width=True)


register_panel("NPC Prices", render)
