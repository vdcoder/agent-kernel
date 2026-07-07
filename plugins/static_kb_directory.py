"""Static context provider that concatenates all markdown files in a directory."""
from __future__ import annotations

from pathlib import Path

from src.interfaces import StaticContextProvider


class StaticKBDirectoryProvider(StaticContextProvider):
    """Reads every ``*.md`` file in *kb_dir* (sorted by name) and returns them
    concatenated as a single static context block.

    Files are joined with a clear separator so the LLM can distinguish topics.
    """

    def __init__(self, kb_dir: str | Path) -> None:
        self._dir = Path(kb_dir)

    def get(self) -> str:
        if not self._dir.is_dir():
            return ""
        files = sorted(self._dir.glob("*.md"))
        if not files:
            return ""
        parts = []
        for f in files:
            text = f.read_text(encoding="utf-8").strip()
            if text:
                parts.append(f"{text}")
        return "\n\n".join(parts)
