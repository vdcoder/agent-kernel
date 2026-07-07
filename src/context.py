"""Context assembly: builds system prompt and per-turn message list."""
from __future__ import annotations

import json
from pathlib import Path

from src.config import Config
from src.interfaces import StaticContextProvider, DynamicContextProvider, MemoryProvider


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _backfill_tool_names(history: list[dict]) -> list[dict]:
    """Sanitize history so the Gemini API never receives a malformed tool exchange.

    Problems handled:
    1. Tool result with missing ``name`` — backfill from the matching assistant
       ``tool_calls`` entry.
    2. Orphaned tool result — the assistant that issued the call was evicted;
       the tool result has no anchor and must be dropped.
    3. Leading non-user messages — Gemini requires ``contents[0]`` to be a user
       turn; trim anything that precedes the first user message.
    """
    # Build a map: tool_call_id → function name, from every assistant message
    id_to_name: dict[str, str] = {}
    for msg in history:
        for tc in msg.get("tool_calls") or []:
            call_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
            fn      = (tc.get("function", {}) if isinstance(tc, dict) else {})
            name    = fn.get("name", "") if isinstance(fn, dict) else getattr(fn, "name", "")
            if call_id and name:
                id_to_name[call_id] = name

    # Identify orphans: tool results whose tool_call_id has no live assistant
    orphan_ids: set[str] = set()
    for msg in history:
        if msg.get("role") != "tool":
            continue
        tc_id = msg.get("tool_call_id", "")
        if tc_id not in id_to_name:
            orphan_ids.add(tc_id)
        elif not msg.get("name"):
            msg["name"] = id_to_name[tc_id]   # backfill in-place

    if orphan_ids:
        history = [
            m for m in history
            if not (m.get("role") == "tool" and m.get("tool_call_id") in orphan_ids)
        ]

    # Trim leading non-user messages (Gemini requires contents[0] to be a user turn)
    while history and history[0].get("role") != "user":
        history.pop(0)

    return history

class ContextManager:
    """Assembles the system prompt and per-turn message list for each agent turn.

    The system prompt (stable prefix) includes:
      - base instructions + tool descriptions
      - assistant's knowledge base and bible
      - assistant's memory for the guest

    The message list (dynamic, changes every turn) includes:
      - rolling conversation summary
      - last N verbatim conversation turns
      - the new user message
    """

    def __init__(
        self,
        config: Config,
        chats_dir: str | Path,
        guest_id: str,
        bible_provider: StaticContextProvider | None = None,
        extra_static_providers: list[StaticContextProvider] | None = None,
        extra_dynamic_providers: list[DynamicContextProvider] | None = None,
        dynamic_context_provider: DynamicContextProvider | None = None,
        memory_provider: MemoryProvider | None = None,
    ) -> None:
        self.config = config
        self._chats_dir = Path(chats_dir)
        self._chats_dir.mkdir(parents=True, exist_ok=True)
        self._guest_id = guest_id
        self._bible_provider = bible_provider
        self._extra_static_providers: list[StaticContextProvider] = extra_static_providers or []
        self._dynamic_context_provider = dynamic_context_provider
        self._extra_dynamic_providers: list[DynamicContextProvider] = extra_dynamic_providers or []
        self._memory_provider = memory_provider

    # ------------------------------------------------------------------
    # Persistence  (db/chats/{guest_id}_*.json/md)
    # ------------------------------------------------------------------

    def load_conversation_history(self) -> list[dict]:
        p = self._chats_dir / f"{self._guest_id}_history.json"
        if not p.exists():
            return []
        history = json.loads(p.read_text(encoding="utf-8"))
        return _backfill_tool_names(history)

    def save_conversation_history(self, history: list[dict]) -> None:
        _atomic_write(
            self._chats_dir / f"{self._guest_id}_history.json",
            json.dumps(history, ensure_ascii=False, indent=2),
        )

    def load_conversation_summary(self) -> str:
        p = self._chats_dir / f"{self._guest_id}_summary.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def save_conversation_summary(self, text: str) -> None:
        _atomic_write(self._chats_dir / f"{self._guest_id}_summary.md", text)

    # ------------------------------------------------------------------
    # Prompt assembly
    # ------------------------------------------------------------------

    def build_system_prompt(self, base: str) -> str:
        """Build the stable system prompt prefix.

        Ordered from most stable (instructions) to least stable (summaries)
        to maximise KV-cache hit rate when using slot-pinned local inference.
        """
        parts = [f"<system_instructions_tools>\n{base}\n</system_instructions_tools>"]

        static = self._bible_provider.get() if self._bible_provider else ""
        if static:
            parts.append(f"<static_context>\n{static}\n</static_context>")

        for provider in self._extra_static_providers:
            extra = provider.get()
            if extra:
                parts.append(f"<static_context>\n{extra}\n</static_context>")

        dynamic = self._dynamic_context_provider.get() if self._dynamic_context_provider else ""
        dynamic_parts = [dynamic] if dynamic else []
        for provider in self._extra_dynamic_providers:
            extra = provider.get()
            if extra:
                dynamic_parts.append(extra)
        if dynamic_parts:
            parts.append(f"<dynamic_context>\n{'\n\n'.join(dynamic_parts)}\n</dynamic_context>")

        memory = self._memory_provider.get() if self._memory_provider else ""
        if memory.strip():
            parts.append(f"<user_memory>\n{memory.strip()}\n</user_memory>")

        return "\n\n".join(parts)

    def build_messages(
        self,
        history: list[dict],
        conversation_summary: str,
        user_message: str,
    ) -> list[dict]:
        """Build the per-turn message list as a natural conversation.

        Structure (keep_last_n = N):

          user : Can you please summarize the conversation up to this point?
          asst : So far we have talked about this: {summary}
                 Also, here is what I remember about you: {memory}
          user : history turn N-keep_last_n   ─┐ verbatim
          asst : history turn N-keep_last_n+1  │ turns
          …                                    │
          user : history turn N               ─┘
          asst : history turn N+1
          user : {current message}             ← always last
        """
        messages: list[dict] = []

        # Inject summary as the first natural exchange (memory is in the system prompt)
        if conversation_summary.strip():
            messages.append({
                "role": "user",
                "content": "Can you please summarize the conversation up to this point?",
            })
            messages.append({
                "role": "assistant",
                "content": f"So far we have talked about this:\n{conversation_summary.strip()}",
            })

        # Verbatim history turns (already trimmed to keep_last_n by the REPL)
        messages.extend(history)

        # Current user message — always last
        messages.append({"role": "user", "content": user_message})
        return messages
