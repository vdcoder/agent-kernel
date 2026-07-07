"""Core agent loop: at most one MCP tool call, optional memory update."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.interfaces import MemoryProvider, Tool, UserInterfaceProvider
    from src.llm import LLMClient

# Built-in schema — injected whenever a memory_provider is present.
_UPDATE_MEMORY_SCHEMA: dict = {
    "type": "function",
    "function": {
        "name": "update_memory",
        "description": (
            "Rewrite the agent memory with new content. Call this when you learn "
            "something about the user that should persist across sessions. "
            "The supplied text replaces the previous memory entirely."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "memory": {
                    "type": "string",
                    "description": "Full replacement text for the memory.",
                },
            },
            "required": ["memory"],
        },
    },
}


def _serialize_tool_calls(tool_calls: list) -> list[dict]:
    # Use model_dump() so vendor-specific extra fields (e.g. Gemini's
    # thought_signature) are preserved in the message history and echoed
    # back correctly on the next API call.
    return [tc.model_dump() for tc in tool_calls]


def _apply_memory_update(tc, memory_provider: "MemoryProvider") -> str:
    """Save the memory update and return the new memory text."""
    args = json.loads(tc.function.arguments)
    new_memory = args.get("memory", "")
    memory_provider.save(new_memory)
    return new_memory


def run_turn(
    llm: "LLMClient",
    messages: list[dict],
    system: str,
    tools: "list[Tool]",
    memory_provider: "MemoryProvider | None" = None,
    ui: "UserInterfaceProvider | None" = None,
) -> tuple[list[dict], str]:
    """Execute one agent turn with at most one MCP tool call.

    chat(all schemas)
      → if MCP tool:    run it   → chat(mem schema)
      → if mem update:  save it  → chat(no schemas)
      → respond
    """
    if ui is None:
        from plugins.ui_rich_cli import RichCLIProvider
        ui = RichCLIProvider()

    mcp_schemas = [t.schema() for t in tools]
    mem_schema = [_UPDATE_MEMORY_SCHEMA] if memory_provider is not None else []
    tool_index = {t.name: t for t in tools}

    # ── Call 1: all tools available ──────────────────────────────────────
    with ui.status("[bold blue]Thinking…[/bold blue]"):
        r = llm.chat(messages, system, tool_schemas=mcp_schemas + mem_schema)
    msg = r.choices[0].message
    tcs = msg.tool_calls or []
    msg_dict: dict = {"role": "assistant", "content": msg.content or None}
    if tcs:
        msg_dict["tool_calls"] = _serialize_tool_calls(tcs)
    messages.append(msg_dict)

    # ── If MCP tool: run it, then re-call with only mem schema ──────────
    if tcs and tcs[0].function.name != "update_memory":
        tc = tcs[0]
        tool = tool_index.get(tc.function.name)
        if tool is None:
            result = f"[error] Unknown tool: {tc.function.name}"
        else:
            ui.show_tool_call(tc.function.name, tc.function.arguments)
            if tool.requires_approval and not ui.ask_confirm(tc.function.name, tc.function.arguments):
                result = "[declined] User did not approve this action."
                messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.function.name, "content": result})
                ui.show_tool_result(tc.function.name, result)
                with ui.status("[bold blue]Processing…[/bold blue]"):
                    r = llm.chat(messages, system, tool_schemas=mem_schema)
                msg = r.choices[0].message
                messages.append({"role": "assistant", "content": msg.content or None})
                ui.show_response(msg.content or "")
                return messages, msg.content or ""
            with ui.status(f"[bold cyan]Running {tc.function.name}…[/bold cyan]"):
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError as exc:
                    result = f"[error] Could not parse tool arguments: {exc}"
                else:
                    try:
                        result = tool.run(args)
                    except Exception as exc:
                        result = f"[error] Tool '{tc.function.name}' raised an unexpected error: {exc}"
            ui.show_tool_result(tc.function.name, result)
        messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.function.name, "content": result})

        with ui.status("[bold blue]Processing…[/bold blue]"):
            r = llm.chat(messages, system, tool_schemas=mem_schema)
        msg = r.choices[0].message
        tcs = msg.tool_calls or []
        msg_dict = {"role": "assistant", "content": msg.content or None}
        if tcs:
            msg_dict["tool_calls"] = _serialize_tool_calls(tcs)
        messages.append(msg_dict)

    # ── If memory update: save it, then re-call with no tools ───────────
    if tcs and tcs[0].function.name == "update_memory":
        if memory_provider is not None:
            new_memory = _apply_memory_update(tcs[0], memory_provider)
        else:
            new_memory = json.loads(tcs[0].function.arguments).get("memory", "")
        ui.show_memory_update(new_memory)
        messages.append({"role": "tool", "tool_call_id": tcs[0].id, "name": tcs[0].function.name, "content": "Memory updated."})

        with ui.status("[bold blue]Responding…[/bold blue]"):
            r = llm.chat(messages, system, tool_schemas=[])
        msg = r.choices[0].message
        messages.append({"role": "assistant", "content": msg.content or None})

    # ── Final response ───────────────────────────────────────────────────
    text = msg.content or ""
    ui.show_response(text)
    return messages, text
