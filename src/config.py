"""Configuration dataclasses loaded from config.toml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore


@dataclass
class LLMConfig:
    """OpenAI-compatible endpoint settings.

    Works with llama.cpp (--server), Ollama, LM Studio, or any endpoint
    that implements the OpenAI Chat Completions API.
    """

    base_url: str = "http://localhost:8080/v1"
    model: str = "local"
    api_key: str = "not-needed"
    max_tokens: int = 4096
    temperature: float = 0.3
    # llama.cpp KV-cache slot IDs — set to -1 to disable slot pinning.
    # Requires --parallel 2 on the server for separate chat/summarise slots.
    local_chat_kvslot: int = 0
    local_summarize_kvslot: int = 1
    local_generic_kvslot: int = 2


@dataclass
class SearchConfig:
    """Web search behaviour."""

    max_results: int = 5
    max_snippet_chars: int = 300


@dataclass
class MCPServerConfig:
    """Connection parameters for one MCP server."""

    name: str = ""
    transport: str = "stdio"              # "stdio" or "sse"
    command: str = ""                     # stdio: executable path or name
    args: list = field(default_factory=list)       # stdio: argument list
    env: dict = field(default_factory=dict)        # stdio: extra env vars
    url: str = ""                         # sse: endpoint URL


@dataclass
class AgentConfig:
    """Agent loop settings."""

    keep_last_n: int = 6          # verbatim turns to keep in history window
    max_tool_iterations: int = 6  # tool-call cap per turn
    memory_max_chars: int = 4000  # rolling cap on agent_memory.md
    summary_max_chars: int = 3000 # rolling cap on conversation_summary.md


@dataclass
class Config:
    """Top-level configuration object."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    mcp_servers: list = field(default_factory=list)  # list[MCPServerConfig]

    @classmethod
    def load(cls, path: str = "config.toml") -> "Config":
        """Load config from *path*; return defaults if the file is absent."""
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        cfg = cls()
        if "llm" in data:
            cfg.llm = LLMConfig(**data["llm"])
        if "search" in data:
            cfg.search = SearchConfig(**data["search"])
        if "agent" in data:
            cfg.agent = AgentConfig(**data["agent"])
        if "mcp_servers" in data:
            cfg.mcp_servers = [MCPServerConfig(**s) for s in data["mcp_servers"]]
        return cfg
