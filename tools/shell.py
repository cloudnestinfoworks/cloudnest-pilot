"""Shell command execution tool.

This is the most dangerous tool. Every call requires user confirmation.
Commands are logged to ~/.ocp-agent/history.log with timestamps.

Never passes commands through a shell interpreter — uses argv lists to
avoid injection. Claude is instructed to pass args as a list.
"""
from __future__ import annotations

import datetime
import shlex
import subprocess
from pathlib import Path

from .registry import tool


# Commands we will categorically refuse no matter what Claude says.
# These exist as a backstop — the user is supposed to catch bad commands
# before approving, but humans get tired and click y too fast.
_HARD_BLOCK_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    ":(){ :|:& };:",
    "mkfs.",
    "dd if=/dev/zero of=/dev/",
    "> /dev/sda",
    "chmod -R 777 /",
]

_HISTORY_LOG_PATH: Path | None = None


def set_history_log(path: Path) -> None:
    """Called by core.py at startup to point at the config's history log."""
    global _HISTORY_LOG_PATH
    _HISTORY_LOG_PATH = path


def _log_command(argv: list[str], cwd: str | None, result: str) -> None:
    if _HISTORY_LOG_PATH is None:
        return
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    cmd = " ".join(shlex.quote(a) for a in argv)
    line = f"[{ts}] cwd={cwd or '.'} cmd={cmd}\n"
    try:
        with _HISTORY_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + result + "\n---\n")
    except (OSError, UnicodeDecodeError):
        # History logging is best-effort; never crash the agent on it.
        pass


@tool(
    name="run_shell",
    description=(
        "Execute a shell command on the user's machine. Every command "
        "requires the user's explicit confirmation before running. "
        "Pass the command as an argv list (e.g. ['aws', 'sts', "
        "'get-caller-identity']) — do NOT pass a single string with "
        "pipes or shell operators. The command runs with a 10 minute "
        "timeout by default. Return value includes stdout, stderr, and "
        "exit code."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "argv": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Command and its arguments, as a list. e.g. ['ls', '-la', '/tmp']",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command. Defaults to the user's current directory.",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Timeout in seconds. Default 600. Use longer for openshift-install (~3600).",
                "default": 600,
            },
            "purpose": {
                "type": "string",
                "description": "One-line explanation of what this command accomplishes, shown to the user in the confirmation prompt.",
            },
        },
        "required": ["argv", "purpose"],
    },
    requires_confirmation=True,
)
def run_shell(
    argv: list[str],
    purpose: str,
    cwd: str | None = None,
    timeout_seconds: int = 600,
) -> str:
    """Run a command. Called AFTER user confirms in the UI."""

    # Final safety backstop — should have been caught by the UI already.
    joined = " ".join(argv)
    for bad in _HARD_BLOCK_PATTERNS:
        if bad in joined:
            return (
                f"REFUSED TO RUN: command matched hard-block pattern '{bad}'. "
                "The agent has a hard-coded blocklist of commands that will "
                "never be executed regardless of user confirmation."
            )

    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        result = f"TIMEOUT after {timeout_seconds}s. The command is still running in the background or may have been killed."
        _log_command(argv, cwd, result)
        return result
    except FileNotFoundError as e:
        result = f"COMMAND NOT FOUND: {argv[0]}\n{e}"
        _log_command(argv, cwd, result)
        return result

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    exit_code = proc.returncode

    # Truncate huge outputs so we don't blow Claude's context.
    MAX_OUT = 20000
    if len(stdout) > MAX_OUT:
        stdout = stdout[: MAX_OUT // 2] + f"\n[... {len(stdout) - MAX_OUT} chars truncated ...]\n" + stdout[-MAX_OUT // 2 :]
    if len(stderr) > MAX_OUT:
        stderr = stderr[: MAX_OUT // 2] + f"\n[... truncated ...]\n" + stderr[-MAX_OUT // 2 :]

    result = (
        f"Exit code: {exit_code}\n"
        f"--- stdout ---\n{stdout}\n"
        f"--- stderr ---\n{stderr}"
    )
    _log_command(argv, cwd, result)
    return result
