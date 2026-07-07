"""Static file-based context provider — reads a markdown file as the agent bible."""
from __future__ import annotations

from pathlib import Path

from src.interfaces import StaticContextProvider


class StaticFileBibleProvider(StaticContextProvider):
    """Returns the contents of a markdown file as the agent's static context.

    Points to ``<project_dir>/assistant_bible.md`` by default, but accepts
    any path so the same provider works with arbitrary file layouts.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def get(self) -> str:
        return self._path.read_text(encoding="utf-8") if self._path.exists() else ""
