"""Abstract interfaces for Agent Kernel components."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TState = TypeVar("TState")


class StaticContextProvider(ABC):
    """Stable, infrequently-changing context injected early in the system prompt.

    Ideal for persona, rules, and reference material whose text rarely changes
    turn-to-turn (good KV-cache candidate on local models).
    """

    @abstractmethod
    def get(self) -> str:
        """Return the static context text. Empty string means nothing to inject."""
        ...


class Runtime(Generic[TState]):
    """Thin, generic session-state carrier — the ``void *ctx`` of the agent world.

    The framework passes ``Runtime[T]`` around without ever inspecting T.
    App-level code always uses a concrete alias (e.g. ``Runtime[AppState]``)
    so the full type is known statically with no casting required.
    """

    def __init__(self, state: TState) -> None:
        self.state: TState = state


class DynamicContextProvider(ABC):
    """Volatile context injected after static context in the system prompt.

    Use this for data that changes every turn or session — current time,
    live configuration, per-request state — where KV-cache reuse is not
    expected.
    """

    @abstractmethod
    def get(self) -> str:
        """Return the dynamic context text. Empty string means nothing to inject."""
        ...


class MemoryProvider(ABC):
    """Supplies the agent's per-session memory for a given runtime.

    Implementations decide how and where memory is stored — a file,
    a database, an in-memory store, or generated on the fly.
    """

    @abstractmethod
    def get(self) -> str:
        """Return the current memory text as a string.

        An empty string means no memory is available.
        """
        ...

    @abstractmethod
    def save(self, text: str) -> None:
        """Persist *text* as the new memory, replacing the previous content entirely."""
        ...


class Tool(ABC):
    """A callable tool the agent can invoke during a turn.

    Implement this in ``plugins/tools/`` to add new capabilities.
    The name must match the ``name`` field in the returned schema.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier used in the function-calling schema."""
        ...

    @abstractmethod
    def schema(self) -> dict:
        """Return the OpenAI-compatible function-calling schema dict."""
        ...

    @abstractmethod
    def run(self, args: dict) -> str:
        """Execute the tool with *args* and return a plain-text result."""
        ...

    @property
    def requires_approval(self) -> bool:
        """Return True to require explicit Y/N user confirmation before run().

        Override in any tool that performs a real-world action.
        """
        return False


class UserInterfaceProvider(ABC):
    """Abstracts every user-facing interaction so the agent core stays UI-agnostic.

    Implement this in ``plugins/`` to swap the entire look-and-feel — CLI,
    web, voice, or any other surface — without touching agent logic.
    """

    # ── input ────────────────────────────────────────────────────────────

    @abstractmethod
    def ask_input(self) -> str:
        """Block until the user sends a message and return it.

        Raise ``EOFError`` or ``KeyboardInterrupt`` to signal that the
        session should end.
        """
        ...

    @abstractmethod
    def ask_confirm(self, title: str, detail: str) -> bool:
        """Show *title* and *detail*, ask yes/no, return True for confirmed."""
        ...

    @abstractmethod
    def ask_guest_id(self, prompt: str, default: str) -> str:
        """Ask the user to identify themselves before the session starts.

        Must be called once, before ``ask_input``, so the runtime can be
        fully initialised with the guest's identity.  Return *default* if
        the user provides no input.
        """
        ...

    # ── output ───────────────────────────────────────────────────────────

    @abstractmethod
    def show_response(self, text: str) -> None:
        """Render the assistant's final text response."""
        ...

    @abstractmethod
    def show_tool_call(self, name: str, arguments: str) -> None:
        """Display a tool invocation before it runs."""
        ...

    @abstractmethod
    def show_tool_result(self, name: str, result: str) -> None:
        """Display the result returned by a tool."""
        ...

    @abstractmethod
    def show_memory_update(self, new_memory: str) -> None:
        """Display the full new memory content after an update_memory call."""
        ...

    @abstractmethod
    def show_info(self, message: str) -> None:
        """Show a neutral informational or status message."""
        ...

    @abstractmethod
    def show_warning(self, message: str) -> None:
        """Show a warning that the user should be aware of."""
        ...

    @abstractmethod
    def show_error(self, message: str) -> None:
        """Show an error message."""
        ...

    @abstractmethod
    def show_banner(
        self,
        model: str,
        base_url: str,
    ) -> None:
        """Display the application startup banner."""
        ...

    # ── status indicator ─────────────────────────────────────────────────

    @abstractmethod
    def status(self, label: str):
        """Return a context manager that shows a loading indicator while active."""
        ...

    # ── session lifecycle ────────────────────────────────────────────────

    def start(self, run_session_fn, config) -> None:
        """Launch a session using this provider.

        The default implementation calls ``run_session_fn(config, self)``
        directly (synchronous, single session).  Providers that own their
        own event loop or server (e.g. a web server) should override this
        to manage the lifecycle themselves.
        """
        run_session_fn(config, self)
