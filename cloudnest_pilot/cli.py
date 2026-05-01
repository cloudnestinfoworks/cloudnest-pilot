"""Terminal UI for the OCP agent.

Clean chat loop with syntax-highlighted command previews and tool diffs.
"""
from __future__ import annotations

import json
import sys

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Prompt

from .config import Config
from .core import AgentSession, PendingToolCall


console = Console()


def print_banner() -> None:
    console.print()
    console.print(
        "[bold cyan]╭─────────────────────────────────────────────╮[/bold cyan]"
    )
    console.print(
        "[bold cyan]│[/bold cyan]  [bold]Cloudnest Pilot[/bold]    "
        "[dim]conversational OpenShift copilot[/dim]    [bold cyan]│[/bold cyan]"
    )
    console.print(
        "[bold cyan]╰─────────────────────────────────────────────╯[/bold cyan]"
    )
    console.print()
    console.print(
        "[dim]Type your request. Type /quit to exit, /history to dump the "
        "conversation.[/dim]"
    )
    console.print()


def render_assistant_text(text: str) -> None:
    console.print(Panel(Markdown(text), border_style="cyan", title="Agent"))


def render_tool_result(tool_name: str, output: str) -> None:
    preview = output if len(output) < 3000 else output[:1500] + "\n[...truncated...]\n" + output[-1500:]
    console.print(
        Panel(
            preview,
            title=f"[dim]{tool_name} result[/dim]",
            border_style="dim",
        )
    )


def confirm_tool_call(call: PendingToolCall) -> bool:
    """Show the user a tool call and ask for yes/no."""
    name = call.tool_name
    inp = call.tool_input

    if name == "run_shell":
        argv = inp.get("argv", [])
        purpose = inp.get("purpose", "(no purpose given)")
        cwd = inp.get("cwd", ".")
        timeout = inp.get("timeout_seconds", 600)
        cmd_str = " ".join(_shlex_quote(a) for a in argv)
        body = (
            f"[bold]Purpose:[/bold] {purpose}\n"
            f"[bold]Command:[/bold]\n"
        )
        console.print(
            Panel(
                body,
                title="[yellow]⚠ Approval needed: shell command[/yellow]",
                border_style="yellow",
            )
        )
        console.print(Syntax(cmd_str, "bash", theme="monokai", padding=1))
        console.print(f"[dim]cwd={cwd}  timeout={timeout}s[/dim]")
    elif name == "write_file":
        path = inp.get("path", "(no path)")
        purpose = inp.get("purpose", "(no purpose)")
        content = inp.get("content", "")
        preview = content if len(content) < 800 else content[:800] + "\n[...truncated...]"
        lang = _guess_language(path)
        console.print(
            Panel(
                f"[bold]Purpose:[/bold] {purpose}\n[bold]Path:[/bold] {path}\n[bold]Size:[/bold] {len(content)} chars",
                title="[yellow]⚠ Approval needed: write file[/yellow]",
                border_style="yellow",
            )
        )
        console.print(Syntax(preview, lang, theme="monokai", padding=1))
    else:
        body = json.dumps(inp, indent=2, default=str)
        console.print(
            Panel(
                Syntax(body, "json", theme="monokai"),
                title=f"[yellow]⚠ Approval needed: {name}[/yellow]",
                border_style="yellow",
            )
        )

    answer = Prompt.ask(
        "[bold yellow]Run this?[/bold yellow] (y=yes, n=no, e=edit)",
        choices=["y", "n", "e"],
        default="n",
    )
    if answer == "e" and name == "run_shell":
        # Simple inline edit for shell commands.
        original = " ".join(_shlex_quote(a) for a in inp.get("argv", []))
        new = Prompt.ask(f"[cyan]Edit command[/cyan]", default=original)
        if new != original:
            try:
                import shlex
                call.tool_input["argv"] = shlex.split(new)
                console.print(f"[dim]Using: {new}[/dim]")
                return True
            except ValueError as e:
                console.print(f"[red]Invalid shell syntax: {e}[/red]")
                return False
        return True
    return answer == "y"


def _shlex_quote(s: str) -> str:
    import shlex
    return shlex.quote(s)


def _guess_language(path: str) -> str:
    p = path.lower()
    if p.endswith(".yaml") or p.endswith(".yml"):
        return "yaml"
    if p.endswith(".json"):
        return "json"
    if p.endswith(".py"):
        return "python"
    if p.endswith(".sh"):
        return "bash"
    return "text"


def run_cli(config: Config) -> None:
    session = AgentSession(config)
    print_banner()

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/bold green]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            return

        if not user_input.strip():
            continue

        if user_input.strip() == "/quit":
            console.print("[dim]Goodbye.[/dim]")
            return

        if user_input.strip() == "/history":
            console.print(Panel(session.dump_conversation(), title="Conversation"))
            continue

        try:
            turn = session.send_user_message(user_input)
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Error calling Claude: {e}[/red]")
            continue

        # Loop: print texts, ask for confirmations, show tool results,
        # call back until Claude reaches end_turn.
        while True:
            for text in turn.texts:
                render_assistant_text(text)
            for result in turn.auto_tool_results:
                render_tool_result(result["tool"], result["output"])

            if not turn.pending_tools:
                break  # Done with this turn.

            confirmed: list[PendingToolCall] = []
            denied: list[PendingToolCall] = []
            for call in turn.pending_tools:
                if confirm_tool_call(call):
                    confirmed.append(call)
                else:
                    denied.append(call)

            try:
                turn = session.continue_after_confirmation(confirmed, denied)
            except Exception as e:  # noqa: BLE001
                console.print(f"[red]Error: {e}[/red]")
                break


# ──────────────────────────────────────────────────────────────────────────
# Console entry point — invoked by `cloudnest-pilot` after pip install
# ──────────────────────────────────────────────────────────────────────────


def main() -> int:
    """Entry point for the `cloudnest-pilot` console script.

    Parses command-line arguments and dispatches to CLI, web, or demo mode.
    """
    import argparse
    import sys

    from . import __version__

    parser = argparse.ArgumentParser(
        prog="cloudnest-pilot",
        description="AI copilot for deploying and managing OpenShift clusters.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run the rich-formatted terminal interface",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Run the web UI on http://localhost:8765 (default)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Demo mode — runs with canned responses, no API key needed",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override WEB_PORT for the web UI (default: 8765)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"cloudnest-pilot {__version__}",
    )
    args = parser.parse_args()

    # Demo mode: bypass API key check entirely
    if args.demo:
        print("\n  Cloudnest Pilot — DEMO MODE")
        print("  " + "─" * 40)
        print("  Running with canned responses. No API key required.")
        print()

        from .web import run_web_demo
        port = args.port or 8765
        try:
            run_web_demo(port=port)
        except KeyboardInterrupt:
            print("\nGoodbye.")
        return 0

    # Real mode: load config (validates API key)
    try:
        from .config import Config
        config = Config.load()
    except SystemExit as e:
        print(f"\n{e}\n")
        print("Tip: try `cloudnest-pilot --demo` to try without an API key.")
        return 1

    if args.port:
        config.web_port = args.port

    if args.cli:
        try:
            run_cli(config)
        except KeyboardInterrupt:
            print("\nGoodbye.")
        return 0

    # Default: web UI
    from .web import run_web
    try:
        run_web(config)
    except KeyboardInterrupt:
        print("\nGoodbye.")
    return 0
