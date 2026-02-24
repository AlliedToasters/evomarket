"""Panel registry — lives in its own module to avoid __main__ identity issues."""

from __future__ import annotations

from collections.abc import Callable

PANELS: dict[str, Callable[[str], None]] = {}


def register_panel(name: str, render_func: Callable[[str], None]) -> None:
    """Register a visualization panel."""
    PANELS[name] = render_func
