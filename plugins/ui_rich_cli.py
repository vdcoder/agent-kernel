"""Rich-powered CLI implementation of UserInterfaceProvider."""
from __future__ import annotations

from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text

from src.interfaces import UserInterfaceProvider

_BOOK_ART = (
    "      [bold cyan]                __/___            [/bold cyan]    \n"
    "      [bold cyan]          _____/______|           [/bold cyan]    \n"
    r"      [bold cyan]  _______/_____\_______\_____     [/bold cyan]    " + "\n"
    r"      [bold cyan]  \              < < <       |    [/bold cyan]    " + "\n"
    "      [bold cyan]~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[/bold cyan]    \n"
)


class RichCLIProvider(UserInterfaceProvider):
    """All user interaction rendered with Rich in the terminal."""

    def __init__(self) -> None:
        self._console = Console()

    # ── input ────────────────────────────────────────────────────────────

    def ask_input(self) -> str:
        """Prompt for input; handle the triple-quote multi-line mode internally."""
        text = Prompt.ask("\n[bold green]you ❯[/bold green]").strip()
        if text != '"""':
            return text
        self._console.print(
            '[dim]Multi-line mode — paste your text, '
            'then type [bold]"""[/bold] on its own line to send[/dim]'
        )
        lines: list[str] = []
        try:
            while True:
                line = input()
                if line.strip() == '"""':
                    break
                lines.append(line)
        except (KeyboardInterrupt, EOFError):
            self._console.print("[yellow]Multi-line input cancelled[/yellow]")
            return ""
        return "\n".join(lines).strip()

    def ask_confirm(self, title: str, detail: str) -> bool:
        choice = Prompt.ask(
            f"[bold]Confirm [cyan]{title}[/cyan]?[/bold] [dim](y / n)[/dim]",
            choices=["y", "n"],
            default="n",
        )
        return choice == "y"

    def ask_guest_id(self, prompt: str, default: str) -> str:
        self._console.print(f"[dim]{prompt}[/dim]")
        value = Prompt.ask(
            "[bold cyan]Guest ID[/bold cyan]",
            default=default,
        ).strip()
        return value if value else default

    # ── output ───────────────────────────────────────────────────────────

    def show_response(self, text: str) -> None:
        self._console.print(Rule("[dim]assistant[/dim]", style="dim blue"))
        self._console.print(Markdown(text))

    def show_tool_call(self, name: str, arguments: str) -> None:
        self._console.print(Panel(
            f"[bold]{name}[/bold]\n[dim]{arguments}[/dim]",
            title="[bold cyan]⚙ Tool[/bold cyan]",
            border_style="cyan",
        ))

    def show_tool_result(self, name: str, result: str) -> None:
        label = Text()
        label.append("  🧠 ", style="dim")
        label.append(name, style="dim bold")
        label.append("  ", style="dim")
        self._console.print(Padding(label + Text(result, style="dim"), (0, 0, 0, 2)))

    def show_memory_update(self, new_memory: str) -> None:
        self._console.print(Panel(
            Text(new_memory, style="dim"),
            title="[dim]🧠  memory updated[/dim]",
            border_style="dim",
            padding=(0, 1),
        ))

    def show_info(self, message: str) -> None:
        self._console.print(message)

    def show_warning(self, message: str) -> None:
        self._console.print(f"[yellow]⚠  {message}[/yellow]")

    def show_error(self, message: str) -> None:
        self._console.print(f"[red]{message}[/red]")

    def show_banner(
        self,
        model: str,
        base_url: str,
    ) -> None:
        info = Text()
        info.append("\n")
        info.append("AGENT KERNEL\n", style="bold white")
        info.append("─" * 15 + "\n", style="dim blue")
        info.append("model     ", style="dim")
        info.append(f"{model}\n", style="bold")
        info.append("endpoint  ", style="dim")
        info.append(base_url, style="dim")
        self._console.print(Panel(
            Columns([_BOOK_ART, info], padding=(0, 4)),
            border_style="blue",
            padding=(1, 2),
        ))

    # ── status indicator ─────────────────────────────────────────────────

    def status(self, label: str):
        return self._console.status(label)
