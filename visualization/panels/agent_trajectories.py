"""Agent Wealth Trajectories panel — per-agent credit balance over time."""

from __future__ import annotations

import altair as alt
import streamlit as st

from visualization import common, data
from visualization.registry import register_panel


def render(episode_dir: str) -> None:
    """Render the Agent Wealth Trajectories panel."""
    db_path = f"{episode_dir}/episode.sqlite"

    st.title("Agent Wealth Trajectories")

    # ── Load data ────────────────────────────────────────────────────
    snapshots = data.load_agent_snapshots(db_path)
    agent_types = data.load_agent_types(episode_dir)

    if snapshots.empty:
        st.warning("No agent snapshot data available.")
    else:
        # ── Filters ──────────────────────────────────────────────────
        max_tick = int(snapshots["tick"].max())
        start_tick, end_tick = common.tick_range_selector(
            max_tick, key="awt_tick_range"
        )

        agent_ids = sorted(snapshots["agent_id"].unique())
        selected_agents = common.agent_filter(agent_ids, key="awt_agent_filter")

        # ── Prepare chart data ───────────────────────────────────────
        filtered = snapshots[
            (snapshots["tick"] >= start_tick)
            & (snapshots["tick"] <= end_tick)
            & (snapshots["agent_id"].isin(selected_agents))
        ].copy()

        filtered["agent_type"] = filtered["agent_id"].map(agent_types).fillna("unknown")

        # ── Wealth trajectory chart ──────────────────────────────────
        st.subheader("Credit Balance Over Time")

        type_domain = sorted(filtered["agent_type"].unique())
        type_range = [common.get_agent_color(t) for t in type_domain]

        chart = (
            alt.Chart(filtered)
            .mark_line(strokeWidth=1.5, opacity=0.7)
            .encode(
                x=alt.X("tick:Q", title="Tick"),
                y=alt.Y("credits:Q", title="Credits"),
                color=alt.Color(
                    "agent_type:N",
                    title="Agent Type",
                    scale=alt.Scale(domain=type_domain, range=type_range),
                ),
                detail="agent_id:N",
                tooltip=["agent_id:N", "agent_type:N", "tick:Q", "credits:Q"],
            )
        )
        st.altair_chart(chart, use_container_width=True)

    # ── Agent summary table ──────────────────────────────────────────
    st.subheader("Agent Summaries")
    summaries = data.load_agent_summaries(episode_dir)

    # Resolve llm:* types to model names from config
    try:
        config = data.load_config(episode_dir)
        llm_backends = config.get("llm_backends", {})
    except Exception:
        config = {}
        llm_backends = {}

    def _resolve_model(agent_type: str) -> str:
        if agent_type.startswith("llm:"):
            backend_name = agent_type[4:]
            spec = llm_backends.get(backend_name, {})
            return spec.get("model", backend_name)
        if agent_type == "llm":
            # Bare "llm" — try to get model from top-level config
            return config.get("model", "llm")
        return ""

    if summaries.empty:
        st.warning("No agent summary data available (result.json missing or empty).")
    else:
        # Compute additional wealth measures from snapshots
        if not snapshots.empty:
            wealth_stats = (
                snapshots.groupby("agent_id")["credits"]
                .agg(max_credits="max", cumulative_credits="sum")
                .reset_index()
            )
            summaries = summaries.merge(wealth_stats, on="agent_id", how="left")
            summaries["max_credits"] = summaries["max_credits"].fillna(0.0)
            summaries["cumulative_credits"] = summaries["cumulative_credits"].fillna(
                0.0
            )
        else:
            summaries["max_credits"] = 0.0
            summaries["cumulative_credits"] = 0.0

        summaries["model"] = summaries["agent_type"].apply(_resolve_model)

        summaries_sorted = summaries.sort_values("net_worth", ascending=False)
        st.dataframe(
            summaries_sorted,
            use_container_width=True,
            hide_index=True,
            column_config={
                "agent_id": "Agent ID",
                "agent_type": "Type",
                "model": "Model",
                "net_worth": st.column_config.NumberColumn(
                    "Final Net Worth", format="%.2f"
                ),
                "max_credits": st.column_config.NumberColumn(
                    "Max Credits", format="%.2f"
                ),
                "cumulative_credits": st.column_config.NumberColumn(
                    "Cumulative Credits", format="%.1f"
                ),
                "lifetime": st.column_config.NumberColumn("Lifetime", format="%d"),
                "total_trades": st.column_config.NumberColumn("Trades", format="%d"),
                "final_credits": st.column_config.NumberColumn(
                    "Final Credits", format="%.2f"
                ),
                "cause_of_death": "Cause of Death",
            },
        )


register_panel("Agent Wealth Trajectories", render)
