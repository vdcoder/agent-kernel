"""File-based MemoryProvider — stores per-guest memory in db/chats/."""
from __future__ import annotations

from pathlib import Path

from src.interfaces import MemoryProvider
from app.runtime import AppRuntime


class MemoryFileProvider(MemoryProvider):
    """Loads per-guest memory from a markdown file inside *chats_dir*."""

    def __init__(self, chats_dir: str | Path, rt: AppRuntime) -> None:
        chats = Path(chats_dir)
        chats.mkdir(parents=True, exist_ok=True)
        self._path = chats / f"{rt.state.guest_id}_memory.md"

    def get(self) -> str:
        return self._path.read_text(encoding="utf-8") if self._path.exists() else ""

    def save(self, text: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self._path)
