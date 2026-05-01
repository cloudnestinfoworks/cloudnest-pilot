"""Filesystem tools.

read_file is safe — it just reads content.
write_file requires user confirmation because it overwrites.
"""
from __future__ import annotations

from pathlib import Path

from .registry import tool

# Max bytes we'll read from a single file. Prevents the agent from stuffing
# Claude's context with a huge binary file.
_MAX_READ_BYTES = 200_000


@tool(
    name="read_file",
    description=(
        "Read the contents of a text file on the user's machine. Useful "
        "for reading YAML configs, kubeconfigs, pull secrets, install "
        "logs, etc. Returns the file's text content or an error message. "
        "Paths starting with ~ are expanded to the user's home directory."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or ~-relative path to the file.",
            },
            "start_line": {
                "type": "integer",
                "description": "Optional 1-indexed start line to read from.",
                "default": 1,
            },
            "max_lines": {
                "type": "integer",
                "description": "Optional max lines to read. Default 500.",
                "default": 500,
            },
        },
        "required": ["path"],
    },
    requires_confirmation=False,
)
def read_file(path: str, start_line: int = 1, max_lines: int = 500) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"File not found: {p}"
    if not p.is_file():
        return f"Path is not a regular file: {p}"
    try:
        size = p.stat().st_size
        if size > _MAX_READ_BYTES:
            content = p.read_text(encoding="utf-8", errors="replace")[
                : _MAX_READ_BYTES
            ]
            truncated = True
        else:
            content = p.read_text(encoding="utf-8", errors="replace")
            truncated = False
    except PermissionError:
        return f"Permission denied: {p}"
    except UnicodeDecodeError:
        return f"File is binary or uses unsupported encoding: {p}"

    lines = content.splitlines()
    start = max(start_line - 1, 0)
    end = min(start + max_lines, len(lines))
    slice_ = lines[start:end]

    header = f"File: {p} ({size} bytes, {len(lines)} total lines)"
    if truncated:
        header += " [TRUNCATED]"
    if start_line != 1 or end < len(lines):
        header += f" — showing lines {start + 1}..{end}"

    body = "\n".join(slice_)
    return header + "\n" + body


@tool(
    name="write_file",
    description=(
        "Write content to a file. If the file exists it is overwritten. "
        "The user is shown the target path and content preview before "
        "the write happens. Useful for generating install-config.yaml, "
        "saving generated kubeconfigs, etc. Paths starting with ~ are "
        "expanded."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Destination path.",
            },
            "content": {
                "type": "string",
                "description": "Full file content (UTF-8 text).",
            },
            "purpose": {
                "type": "string",
                "description": "One-line explanation, shown to the user in the confirmation prompt.",
            },
        },
        "required": ["path", "content", "purpose"],
    },
    requires_confirmation=True,
)
def write_file(path: str, content: str, purpose: str) -> str:
    p = Path(path).expanduser()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except PermissionError:
        return f"Permission denied: {p}"
    except OSError as e:
        return f"Failed to write {p}: {e}"
    return f"Wrote {len(content)} bytes to {p}"
