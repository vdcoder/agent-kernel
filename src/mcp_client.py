"""MCP server client — connects to MCP servers and wraps their tools as Tool instances."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from src.interfaces import Tool

if TYPE_CHECKING:
    from src.config import MCPServerConfig


def _to_openai_schema(mcp_tool) -> dict:
    """Convert an MCP tool definition to OpenAI function-calling schema."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema,
        },
    }


def _extract_text(result) -> str:
    """Pull plain text out of an MCP CallToolResult."""
    parts = []
    for content in result.content:
        if hasattr(content, "text"):
            parts.append(content.text)
        elif hasattr(content, "data"):
            parts.append(json.dumps(content.data))
        else:
            parts.append(str(content))
    return "\n".join(parts) if parts else ""


class MCPTool(Tool):
    """A Tool backed by a remote MCP server tool.

    Instances are created by MCPClient.list_tools() and call back through
    the same client for execution.
    """

    def __init__(self, mcp_tool_def, client: "MCPClient") -> None:
        self._name = mcp_tool_def.name
        self._schema = _to_openai_schema(mcp_tool_def)
        self._client = client

    @property
    def name(self) -> str:
        return self._name

    def schema(self) -> dict:
        return self._schema

    def run(self, args: dict) -> str:
        return self._client.call_tool(self._name, args)


class MCPClient:
    """Connects to one MCP server (stdio or SSE) and exposes its tools.

    Each public method opens a fresh connection, runs the request, and
    closes the connection.  This keeps the client stateless and avoids
    lifecycle management at the cost of per-call startup overhead — which
    is acceptable for an interactive CLI demo.
    """

    def __init__(self, config: "MCPServerConfig") -> None:
        self._config = config

    # ── transport ────────────────────────────────────────────────────────

    @asynccontextmanager
    async def _session(self):
        """Yield an initialised MCP ClientSession for one request."""
        from mcp import ClientSession

        cfg = self._config
        if cfg.transport == "sse":
            from mcp.client.sse import sse_client
            cm = sse_client(url=cfg.url)
        else:
            from mcp.client.stdio import stdio_client, StdioServerParameters
            params = StdioServerParameters(
                command=cfg.command,
                args=cfg.args or [],
                env=cfg.env or None,
            )
            cm = stdio_client(params)

        async with cm as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    # ── async internals ──────────────────────────────────────────────────

    async def _alist_tools(self) -> list:
        async with self._session() as session:
            result = await session.list_tools()
            return result.tools

    async def _acall_tool(self, name: str, args: dict) -> str:
        async with self._session() as session:
            result = await session.call_tool(name, arguments=args)
            return _extract_text(result)

    # ── public sync API ──────────────────────────────────────────────────

    def list_tools(self) -> list[MCPTool]:
        """Connect, fetch tool definitions, return MCPTool wrappers."""
        mcp_defs = asyncio.run(self._alist_tools())
        return [MCPTool(t, self) for t in mcp_defs]

    def call_tool(self, name: str, args: dict) -> str:
        """Connect, call the named tool, return result as a string."""
        try:
            return asyncio.run(self._acall_tool(name, args))
        except Exception as exc:
            return f"[error] MCP tool '{name}' failed: {exc}"
