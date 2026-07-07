"""App-level runtime state.

The agent framework carries a ``Runtime[T]`` where T is opaque to it.
Here we define the concrete T for this cruise-demo application so that
app-level plugins and tools can access typed state without any casting.

Usage inside app code::

    from app.runtime import AppRuntime, AppState
    from src.interfaces import Runtime

    runtime: AppRuntime            # = Runtime[AppState]
    guest_id = runtime.state.guest_id   # fully typed, no cast needed
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.interfaces import Runtime


@dataclass
class AppState:
    """Per-session application state owned by this cruise demo."""

    guest_id: str = "G100001"
    """The cruise guest identifier for the active session."""

    guest_profile: dict = field(default_factory=dict)
    """Full guest_profiles row loaded from cruise.db at session start."""

    current_query: str = ""
    """The user's current turn message; set before each system-prompt build."""


# Convenience alias — import this in all app-level code instead of
# spelling out Runtime[AppState] every time.
AppRuntime = Runtime[AppState]
