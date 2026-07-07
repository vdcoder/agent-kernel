"""Command-line entry point and interactive REPL."""
from __future__ import annotations

import argparse
import re
import traceback
from pathlib import Path

import openai

from src.agent import run_turn
from src.config import Config
from src.context import ContextManager
from src.llm import LLMClient, SYSTEM_PROMPT_BASE
from src.mcp_client import MCPClient
from src.summarizer import Summarizer
from plugins.static_kb_directory import StaticKBDirectoryProvider
from plugins.dynamic_datetime_now import DatetimeNowProvider
from plugins.memory_file import MemoryFileProvider
from plugins.ui_rich_cli import RichCLIProvider
from src.tool_loader import discover_tools
from src.interfaces import Runtime, UserInterfaceProvider
from app.runtime import AppState
from app.db import load_guest
from app.guest_context import GuestProfileProvider
from plugins.dynamic_rag_context import RAGContextProvider

_SLUG_RE = re.compile(r"[^\w\-]")


# ---------------------------------------------------------------------------
# Slash commands
# ---------------------------------------------------------------------------

def _handle_command(
    cmd: str,
    ctx: ContextManager,
    summarizer: Summarizer,
    ui: UserInterfaceProvider,
    memory,
    last_prompt_ref: list,
) -> None:
    parts = cmd.split()
    verb = parts[0].lower()

    if verb == "/help":
        ui.show_info(
            "/help                    Show this help\n"
            "/memory                  Show current user memory\n"
            "/prompt                  Show the last full system prompt\n"
            "/quit                    Exit\n"
            '"""                      Start/end multi-line input (paste mode)'
        )

    elif verb == "/memory":
        mem = memory.get() if memory is not None else ""
        if mem.strip():
            ui.show_response(mem)
        else:
            ui.show_info("User memory is empty.")

    elif verb == "/prompt":
        data = last_prompt_ref[0] if last_prompt_ref else None
        if not data:
            ui.show_info("No prompt recorded yet — send a message first.")
        elif isinstance(data, dict):
            ui.show_response(_format_prompt_display(data["system"], data["messages"]))
        else:
            ui.show_response(data)  # legacy plain string fallback

    else:
        ui.show_error(f"Unknown command: {verb}. Type /help for help.")


# ---------------------------------------------------------------------------
# Prompt display helper
# ---------------------------------------------------------------------------

def _est_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token (good enough for budgeting)."""
    return max(1, len(text) // 4)


def _format_prompt_display(system: str, messages: list[dict]) -> str:
    """Format the full LLM context (sent + received) as readable XML with token estimates."""
    sys_tokens = _est_tokens(system)

    lines = [f"<system tokens≈{sys_tokens:,}>"]
    lines.append(system)
    lines.append("</system>")

    msg_tokens = 0
    if messages:
        lines.append("")
        lines.append("<messages>")
        for msg in messages:
            role       = msg.get("role", "unknown")
            content    = msg.get("content") or ""
            tool_calls = msg.get("tool_calls")
            tool_id    = msg.get("tool_call_id")

            # Collect all text for this message's token estimate
            msg_text = content
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                    msg_text += fn.get("arguments", "")
            t = _est_tokens(msg_text)
            msg_tokens += t

            open_tag = f'  <message role="{role}" tokens≈{t:,}'
            if tool_id:
                open_tag += f' tool_call_id="{tool_id}"'
            lines.append(open_tag + ">")

            if content:
                lines.append(content)
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                    lines.append(f'    <tool_call name="{fn.get("name","")}">'
                                 + fn.get("arguments", "") + "</tool_call>")
            lines.append("  </message>")
        lines.append("</messages>")

    total = sys_tokens + msg_tokens
    lines.append("")
    lines.append(
        f"<!-- tokens: system≈{sys_tokens:,}  messages≈{msg_tokens:,}  total≈{total:,} -->"
    )

    body = "\n".join(lines)
    return f"```xml\n{body}\n```"


# ---------------------------------------------------------------------------

def run_session(config: Config, ui: UserInterfaceProvider) -> None:
    """Provision all providers and run the REPL loop with the given UI."""
    chats_dir = Path(__file__).parent.parent / "db" / "chats"

    while True:
        guest_id = ui.ask_guest_id("Enter your Guest ID (press Enter to use default)", "G100001")
        profile  = load_guest(guest_id)
        if profile is not None:
            break
        ui.show_error(f"Guest ID '{guest_id}' not found in the database. Please try again.")

    runtime      = Runtime(AppState(guest_id=guest_id, guest_profile=profile))
    guest_ctx    = GuestProfileProvider(runtime)
    kb_dir       = Path(__file__).parent.parent / "db" / "kb"
    bible        = StaticKBDirectoryProvider(kb_dir)
    dynamic      = DatetimeNowProvider()
    memory       = MemoryFileProvider(chats_dir, runtime)
    llm          = LLMClient(config)
    rag          = RAGContextProvider(runtime, llm)

    _tools_dir = Path(__file__).parent.parent / "plugins" / "tools"
    mcp_tools  = discover_tools(_tools_dir)
    ui.show_info(f"[dim]Loaded {len(mcp_tools)} local tool(s): {', '.join(t.name for t in mcp_tools)}[/dim]")
    for srv in config.mcp_servers:
        try:
            client = MCPClient(srv)
            mcp_tools.extend(client.list_tools())
            ui.show_info(f"[dim]MCP server [bold]{srv.name}[/bold] — {len(mcp_tools)} tools loaded[/dim]")
        except Exception as exc:
            ui.show_warning(f"MCP server '{srv.name}' unavailable: {exc}")

    ctx        = ContextManager(config,
                                chats_dir=chats_dir,
                                guest_id=runtime.state.guest_id,
                                bible_provider=bible,
                                extra_static_providers=[guest_ctx],
                                dynamic_context_provider=dynamic,
                                extra_dynamic_providers=[rag],
                                memory_provider=memory)
    summarizer = Summarizer(llm)

    ui.show_banner(config.llm.model, config.llm.base_url)

    if not llm.health_check():
        ui.show_warning(f"LLM not reachable — is your server running on {config.llm.base_url}?")

    ui.show_info('[dim]Type /help for commands · """ for multi-line · /quit to exit[/dim]')

    history = ctx.load_conversation_history()
    summary = ctx.load_conversation_summary()
    keep    = config.agent.keep_last_n * 2
    last_prompt_ref: list[str] = [""]   # updated each turn, read by /prompt

    while True:
        try:
            user_input = ui.ask_input()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit", "/q"):
            break
        if user_input.startswith("/"):
            _handle_command(user_input, ctx, summarizer, ui, memory, last_prompt_ref)
            continue

        runtime.state.current_query = user_input
        system   = ctx.build_system_prompt(SYSTEM_PROMPT_BASE)
        messages = ctx.build_messages(history, summary, user_input)
        n_before = len(messages)

        try:
            _, final_text = run_turn(
                llm, messages, system,
                tools=mcp_tools, memory_provider=memory, ui=ui,
            )
        except openai.APIConnectionError:
            ui.show_error(
                f"Cannot reach the LLM at {config.llm.base_url}. "
                "Is your server running? Check base_url in config.toml."
            )
            continue
        except Exception as exc:
            ui.show_error(f"Error: {exc}")
            ui.show_info(f"[dim]{traceback.format_exc()}[/dim]")
            continue

        # Snapshot the COMPLETE exchange (sent + received) for /prompt
        last_prompt_ref[0] = {
            "system":   system,
            "messages": [dict(m) for m in messages],
        }

        # Save full turn to history: user msg + all assistant/tool msgs from run_turn
        history.append({"role": "user", "content": user_input})
        history.extend(messages[n_before:])

        # Evict oldest complete user-turn when we exceed keep_last_n turns
        while sum(1 for m in history if m.get("role") == "user") > config.agent.keep_last_n:
            evicted: list[dict] = []
            if history and history[0]["role"] == "user":
                evicted.append(history.pop(0))
                while history and history[0]["role"] != "user":
                    evicted.append(history.pop(0))
            if evicted:
                try:
                    summary = summarizer.summarize_conversation(
                        evicted,
                        existing_summary=summary,
                        summary_max_chars=config.agent.summary_max_chars,
                    )
                    # Emergency hard cap: drop oldest content at a sentence boundary
                    if len(summary) > config.agent.summary_max_chars:
                        excess = summary[config.agent.summary_max_chars:]
                        cut    = summary.find(". ")
                        summary = summary[cut + 2:] if cut != -1 else summary[-config.agent.summary_max_chars:]
                except Exception as exc:
                    ui.show_info(f"[dim yellow]Auto-summarize failed: {exc}[/dim yellow]")

        ctx.save_conversation_history(history[-keep:])
        ctx.save_conversation_summary(summary)

    ui.show_info("Goodbye!")
    ctx.save_conversation_history(history[-keep:])
    ctx.save_conversation_summary(summary)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Kernel — interactive assistant")
    parser.add_argument("--config", default="config.toml",
                        help="Path to config.toml (default: config.toml in cwd)")
    parser.add_argument("--web", action="store_true",
                        help="Serve a browser UI instead of the terminal UI")
    parser.add_argument("--port", type=int, default=4000,
                        help="Port for the web UI server (only with --web, default: 4000)")
    args = parser.parse_args()

    config = Config.load(args.config)

    if args.web:
        from plugins.ui_web import WebUIProvider
        ui = WebUIProvider(port=args.port)
    else:
        ui = RichCLIProvider()

    ui.start(run_session, config)


if __name__ == "__main__":
    main()
