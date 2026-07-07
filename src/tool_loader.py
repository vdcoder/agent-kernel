"""Auto-discovers Tool implementations from the plugins/tools directory."""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from src.interfaces import Tool


def discover_tools(tools_dir: Path) -> list[Tool]:
    """Import every non-private .py file in *tools_dir* and return one instance
    of each concrete Tool subclass found.

    Discovery rules:
    - Files starting with ``_`` are skipped.
    - Only classes whose ``__module__`` matches the imported file are collected
      (prevents re-importing Tool itself or classes imported from elsewhere).
    - Classes are instantiated with no arguments; Tool implementations must
      support a zero-argument constructor.
    """
    tools: list[Tool] = []
    for path in sorted(tools_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        module_name = f"plugins.tools.{path.stem}"
        module = importlib.import_module(module_name)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, Tool)
                and cls is not Tool
                and cls.__module__ == module_name
            ):
                tools.append(cls())
    return tools
