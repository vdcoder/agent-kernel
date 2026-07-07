"""DynamicContextProvider that retrieves relevant passages for the current query."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.interfaces import DynamicContextProvider
from app.runtime import AppRuntime
from app.rag import store

if TYPE_CHECKING:
    from src.llm import LLMClient


class RAGContextProvider(DynamicContextProvider):
    """Semantic search over the ingested RAG store, scoped to the current user query.

    Reads ``rt.state.current_query`` (set by the REPL before each turn),
    embeds it with the same LLM client used for chat, and injects the
    top-k most relevant passages into the dynamic context so the model
    can cite them.
    """

    def __init__(self, rt: AppRuntime, llm: "LLMClient", top_k: int = 3) -> None:
        self._rt    = rt
        self._llm   = llm
        self._top_k = top_k

    def get(self) -> str:
        query = self._rt.state.current_query.strip()
        if not query:
            return ""

        # Skip gracefully if the store is empty (not yet ingested).
        sources = store.list_sources()
        if not sources:
            return ""

        try:
            q_emb  = self._llm.embed(query)
            chunks = store.search(q_emb, top_k=self._top_k)
        except Exception as exc:
            return f"<!-- RAG search failed: {exc} -->"

        if not chunks:
            return ""

        lines = ["## Relevant Document Passages"]
        for i, c in enumerate(chunks, 1):
            heading = f" — {c['heading']}" if c.get("heading") else ""
            lines.append(f"\n### [{i}] {c['source_file']}{heading}")
            lines.append(c["text"])

        return "\n".join(lines)
