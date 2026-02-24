"""Time Series panel — macro-economic indicators over simulation ticks."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from visualization import app, common, data

_MILLICREDITS_PER_CREDIT = 1000


def _compute_credit_reservoirs(
    db_path: str, episode_dir: str, start_tick: int, end_tick: int
) -> pd.DataFrame:
    """Compute per-tick credit distribution between agents and system.

    Returns a long-form DataFrame with columns: tick, reservoir, credits.
    """
    config = data.load_config(episode_dir)
    total_supply = config["total_credit_supply"] / _MILLICREDITS_PER_CREDIT

    snapshots = data.load_agent_snapshots(db_path)
    if snapshots.empty:
        tick_metrics = data.load_tick_metrics(db_path)
        ticks = tick_metrics.loc[
            (tick_metrics["tick"] >= start_tick) & (tick_metrics["tick"] <= end_tick),
            "tick",
        ]
        return pd.DataFrame(
            [{"tick": t, "reservoir": "Agent Credits", "credits": 0.0} for t in ticks]
            + [
                {"tick": t, "reservoir": "System Credits", "credits": total_supply}
                for t in ticks
            ]
        )

    agent_credits = (
        snapshots.groupby("tick")["credits"].sum().reset_index(name="agent_credits")
    )
    agent_credits = agent_credits[
        (agent_credits["tick"] >= start_tick) & (agent_credits["tick"] <= end_tick)
    ]
    agent_credits["system_credits"] = total_supply - agent_credits["agent_credits"]

    agents = agent_credits[["tick", "agent_credits"]].rename(
        columns={"agent_credits": "credits"}
    )
    agents["reservoir"] = "Agent Credits"

    system = agent_credits[["tick", "system_credits"]].rename(
        columns={"system_credits": "credits"}
    )
    system["reservoir"] = "System Credits"

    return pd.concat([agents, system], ignore_index=True)


def render(episode_dir: str) -> None:
    """Render the Time Series panel."""
    db_path = f"{episode_dir}/episode.sqlite"

    tick_metrics = data.load_tick_metrics(db_path)
    if tick_metrics.empty:
        st.warning("No tick data available.")
        return

    max_tick = int(tick_metrics["tick"].max())
    start_tick, end_tick = common.tick_range_selector(max_tick, key="ts_tick_range")

    filtered = tick_metrics[
        (tick_metrics["tick"] >= start_tick) & (tick_metrics["tick"] <= end_tick)
    ]

    # 1. Credit Reservoirs (stacked area)
    st.subheader("Credit Reservoirs")
    reservoirs = _compute_credit_reservoirs(db_path, episode_dir, start_tick, end_tick)
    if not reservoirs.empty:
        chart = (
            alt.Chart(reservoirs)
            .mark_area()
            .encode(
                x=alt.X("tick:Q", title="Tick"),
                y=alt.Y("credits:Q", title="Credits", stack=True),
                color=alt.Color(
                    "reservoir:N",
                    title="Reservoir",
                    scale=alt.Scale(
                        domain=["Agent Credits", "System Credits"],
                        range=["#1565C0", "#FF8F00"],
                    ),
                ),
                order=alt.Order("reservoir:N"),
            )
        )
        st.altair_chart(chart, use_container_width=True)

    # 2. Population Count (line)
    st.subheader("Population")
    chart = (
        alt.Chart(filtered)
        .mark_line(color="#2E7D32")
        .encode(
            x=alt.X("tick:Q", title="Tick"),
            y=alt.Y("agents_alive:Q", title="Agents Alive"),
        )
    )
    st.altair_chart(chart, use_container_width=True)

    # 3. Gini Coefficient (line, 0-1)
    st.subheader("Gini Coefficient")
    chart = (
        alt.Chart(filtered)
        .mark_line(color="#AB47BC")
        .encode(
            x=alt.X("tick:Q", title="Tick"),
            y=alt.Y(
                "agent_credit_gini:Q",
                title="Gini",
                scale=alt.Scale(domain=[0, 1]),
            ),
        )
    )
    st.altair_chart(chart, use_container_width=True)

    # 4. Deaths Per Tick (bar)
    st.subheader("Deaths Per Tick")
    chart = (
        alt.Chart(filtered)
        .mark_bar(color="#D32F2F")
        .encode(
            x=alt.X("tick:Q", title="Tick"),
            y=alt.Y("agents_died:Q", title="Deaths"),
        )
    )
    st.altair_chart(chart, use_container_width=True)

    # 5. Trade Volume (line)
    st.subheader("Trade Volume")
    chart = (
        alt.Chart(filtered)
        .mark_line(color="#F57F17")
        .encode(
            x=alt.X("tick:Q", title="Tick"),
            y=alt.Y("total_trade_volume:Q", title="Credits Traded"),
        )
    )
    st.altair_chart(chart, use_container_width=True)


app.register_panel("Time Series", render)
