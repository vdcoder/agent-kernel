"""WebSocket implementation of UserInterfaceProvider.

The agent engine is purely synchronous and expects all UI calls to block
until they have a result.  This provider satisfies that contract by using
a thread-safe queue: the WebSocket receive handler puts messages into the
queue, and ask_input() / ask_confirm() call queue.get() which blocks the
engine thread until a message arrives.  No async coordination or state
machine is needed on the Python side.

Outbound events (server -> browser):
  {"type": "state",         "value": "thinking"|"tool_running"|"idle"}
  {"type": "response",      "text":  "..."}
  {"type": "tool_call",     "name":  "...", "arguments": "..."}
  {"type": "tool_result",   "name":  "...", "result":    "..."}
  {"type": "memory_update", "memory":"..."}
  {"type": "info",          "message":"..."}
  {"type": "warning",       "message":"..."}
  {"type": "error",         "message":"..."}
  {"type": "banner",        "project":"...", "chapter":"...", "model":"...", "base_url":"..."}
  {"type": "confirm",       "title": "...", "detail":   "..."}

Inbound messages (browser -> server):
  Any plain text                -> user utterance, returned by ask_input()
  "__confirm:y" / "__confirm:n" -> resolves a pending ask_confirm()

Minimal integration sketch:
  input_q = queue.Queue()

  def on_ws_message(raw: str):
      input_q.put(raw)

  def send(payload: dict):
      ws.send(json.dumps(payload))

  ui = WebSocketUIProvider(send=send, recv_queue=input_q)
  threading.Thread(target=run_agent_repl, args=(ui,)).start()
"""
from __future__ import annotations

import json
import queue
from contextlib import contextmanager
from typing import Callable

from src.interfaces import UserInterfaceProvider

_CONFIRM_PREFIX  = "__confirm:"
_GUEST_ID_PREFIX = "__guest_id:"
_DISCONNECT      = "__disconnect__"


class WebSocketUIProvider(UserInterfaceProvider):
    """Routes all agent I/O to a browser over WebSocket.

    ``send`` and ``recv_queue`` are the only integration points.
    Everything else is handled internally and the engine never knows
    it is not talking to a terminal.
    """

    def __init__(
        self,
        send: Callable[[dict], None],
        recv_queue: "queue.Queue[str]",
    ) -> None:
        self._send = send
        self._recv = recv_queue

    def _emit(self, payload: dict) -> None:
        try:
            self._send(payload)
        except Exception:
            # WebSocket closed — signal ask_input/ask_confirm to exit
            try:
                self._recv.put_nowait(_DISCONNECT)
            except Exception:
                pass

    # ── input ────────────────────────────────────────────────────────────

    def ask_input(self) -> str:
        self._emit({"type": "state", "value": "idle"})
        while True:
            msg = self._recv.get()          # blocks until browser sends
            if msg == _DISCONNECT:
                raise EOFError("WebSocket disconnected")
            if not msg.startswith(_CONFIRM_PREFIX):
                return msg

    def ask_confirm(self, title: str, detail: str) -> bool:
        self._emit({"type": "confirm", "title": title, "detail": detail})
        while True:
            msg = self._recv.get()          # blocks until browser responds
            if msg == _DISCONNECT:
                raise EOFError("WebSocket disconnected")
            if msg.startswith(_CONFIRM_PREFIX):
                return msg[len(_CONFIRM_PREFIX):].strip().lower() == "y"

    def ask_guest_id(self, prompt: str, default: str) -> str:
        self._emit({"type": "ask_guest_id", "prompt": prompt, "default": default})
        while True:
            msg = self._recv.get()          # blocks until browser responds
            if msg == _DISCONNECT:
                raise EOFError("WebSocket disconnected")
            if msg.startswith(_GUEST_ID_PREFIX):
                value = msg[len(_GUEST_ID_PREFIX):].strip()
                return value if value else default

    # ── output ───────────────────────────────────────────────────────────

    def show_response(self, text: str) -> None:
        # Stop the spinner the moment the response is ready, before rendering it
        self._emit({"type": "state", "value": "idle"})
        self._emit({"type": "response", "text": text})

    def show_tool_call(self, name: str, arguments: str) -> None:
        self._emit({"type": "tool_call", "name": name, "arguments": arguments})

    def show_tool_result(self, name: str, result: str) -> None:
        self._emit({"type": "tool_result", "name": name, "result": result})

    def show_memory_update(self, new_memory: str) -> None:
        self._emit({"type": "memory_update", "memory": new_memory})

    def show_info(self, message: str) -> None:
        self._emit({"type": "info", "message": message})

    def show_warning(self, message: str) -> None:
        self._emit({"type": "warning", "message": message})

    def show_error(self, message: str) -> None:
        self._emit({"type": "error", "message": message})

    def show_banner(self, model: str, base_url: str) -> None:
        self._emit({"type": "banner", "model": model, "base_url": base_url})

    # ── status indicator ─────────────────────────────────────────────────

    @contextmanager
    def status(self, label: str):
        state = "tool_running" if "running" in label.lower() else "thinking"
        self._emit({"type": "state", "value": state, "label": label})
        try:
            yield
        finally:
            pass

