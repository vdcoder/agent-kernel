"""Web UI — serves the agent over a browser WebSocket.

The FastAPI app and all routes are module-level objects (exactly like the
old standalone server.py that worked).  serve() just sets two globals and
calls the blocking uvicorn.run().
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from plugins.ui_websocket import WebSocketUIProvider, _DISCONNECT

_HTML = Path(__file__).parent / "ui_websocket_client.html"

# ── module-level state set by serve() ────────────────────────────────────
_run_session_fn = None
_config         = None

# ── FastAPI app (module level, mirrors old working server.py) ────────────
_app = FastAPI()


@_app.get("/")
async def _index() -> FileResponse:
    return FileResponse(_HTML)


@_app.get("/cruise.png")
async def _cruise_image() -> FileResponse:
    return FileResponse(Path(__file__).parent / "ui_web_cruise96x96.png")


@_app.websocket("/ws")
async def _endpoint(ws: WebSocket) -> None:
    print(f"[WS] endpoint called from {ws.client}", flush=True)
    await ws.accept()
    print("[WS] accepted — handshake complete", flush=True)

    input_q: queue.Queue[str] = queue.Queue()
    loop = asyncio.get_running_loop()

    def send(payload: dict) -> None:
        try:
            f = asyncio.run_coroutine_threadsafe(
                ws.send_text(json.dumps(payload)), loop
            )
            f.result(timeout=10)
        except Exception as e:
            print(f"[WS] send failed: {e}", flush=True)
            try:
                input_q.put_nowait(_DISCONNECT)
            except Exception:
                pass

    ui = WebSocketUIProvider(send=send, recv_queue=input_q)
    threading.Thread(target=_run_session_fn, args=(_config, ui), daemon=True).start()
    print("[WS] session thread started", flush=True)

    try:
        async for msg in ws.iter_text():
            input_q.put(msg)
    except WebSocketDisconnect as e:
        print(f"[WS] disconnected (code={e.code})", flush=True)
        input_q.put(_DISCONNECT)
    except Exception as e:
        print(f"[WS] error: {e}", flush=True)
        input_q.put(_DISCONNECT)


# ── public entry point ───────────────────────────────────────────────────

def serve(config, run_session_fn, host: str = "0.0.0.0", port: int = 4000) -> None:
    """Start the web server.  BLOCKS until the process is killed."""
    import uvicorn
    global _config, _run_session_fn
    _config         = config
    _run_session_fn = run_session_fn
    print(f"\nWeb UI → http://localhost:{port}\n", flush=True)
    uvicorn.run(_app, host=host, port=port, log_level="info")


class WebUIProvider:
    """Web UI provider — owns the FastAPI server lifecycle."""

    def __init__(self, host: str = "0.0.0.0", port: int = 4000) -> None:
        self._host = host
        self._port = port

    def start(self, run_session_fn, config) -> None:
        """Start the web server.  BLOCKS until the process is killed."""
        serve(config, run_session_fn, host=self._host, port=self._port)


