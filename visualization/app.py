"""EvoMarket Visualization Dashboard — Streamlit app shell."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from visualization import data

# ---------------------------------------------------------------------------
# Panel registry
# ---------------------------------------------------------------------------

_PANELS: dict[str, Callable[[str], None]] = {}


def register_panel(name: str, render_func: Callable[[str], None]) -> None:
    """Register a visualization panel.

    Args:
        name: Display name for the sidebar navigation.
        render_func: Function called with the episode directory path as its
            sole argument. It should render its content using Streamlit calls.
    """
    _PANELS[name] = render_func


# ---------------------------------------------------------------------------
# Import panels — each panel calls register_panel() at import time.
# Adding a new panel is a one-line import here.
# ---------------------------------------------------------------------------
import visualization.panels.time_series  # noqa: F401, E402
import visualization.panels.agent_trajectories  # noqa: F401, E402
# import visualization.panels.spatial_graph  # noqa: F401
# import visualization.panels.npc_heatmaps  # noqa: F401


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


def _welcome_page(episode_dir: str | None) -> None:
    """Render the welcome page when no panels are registered."""
    st.title("EvoMarket Dashboard")
    st.info(
        "No visualization panels are loaded. Add panels by importing them in `visualization/app.py`."
    )

    if episode_dir is None:
        return

    result_path = Path(episode_dir) / "result.json"
    if not result_path.exists():
        return

    result = data.load_result(episode_dir)
    st.subheader("Episode Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Ticks", result.get("ticks_executed", "—"))
    col2.metric("Agents alive", result.get("final_agents_alive", "—"))
    col3.metric("Total deaths", result.get("total_deaths", "—"))

    col4, col5, col6 = st.columns(3)
    col4.metric("Total trades", result.get("total_trades", "—"))
    col5.metric("Final Gini", f"{result.get('final_gini', 0):.3f}")
    col6.metric("Mean lifetime", f"{result.get('mean_lifetime', 0):.1f}")


def main() -> None:
    st.set_page_config(page_title="EvoMarket Dashboard", layout="wide")

    # --- Sidebar: episode selection ---
    with st.sidebar:
        st.header("Episode")
        episode_dir = st.text_input(
            "Episode directory",
            help="Path to a simulation output directory containing episode.sqlite",
        )

        db_path: str | None = None
        if episode_dir:
            sqlite_path = Path(episode_dir) / "episode.sqlite"
            if sqlite_path.exists():
                db_path = str(sqlite_path)
                st.success(f"Loaded: {sqlite_path.name}")
            else:
                st.error(f"No episode.sqlite found in {episode_dir}")

    # --- Sidebar: panel navigation ---
    if not _PANELS:
        _welcome_page(episode_dir if db_path else None)
        return

    with st.sidebar:
        st.header("Panels")
        selected = st.radio(
            "Select panel",
            options=list(_PANELS.keys()),
            label_visibility="collapsed",
        )

    # --- Main area ---
    if not episode_dir:
        st.title("EvoMarket Dashboard")
        st.warning("Select an episode directory in the sidebar to begin.")
        return

    if db_path is None:
        st.title("EvoMarket Dashboard")
        st.error(f"No episode.sqlite found in {episode_dir}")
        return

    _PANELS[selected](episode_dir)


if __name__ == "__main__":
    main()
