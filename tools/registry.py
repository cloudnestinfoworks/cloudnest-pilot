"""Tool registry.

This is the central place where all tools the agent can use are registered
and their JSON schemas exported for Claude's tool-use API.

Adding a new tool:
1. Write a function that takes kwargs and returns a string.
2. Decorate it with @tool(name, description, schema).
3. Import it somewhere (usually in cloudnest_pilot/core.py) so the decorator runs.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tool:
    """A single tool the agent can call."""

    name: str
    description: str
    input_schema: dict[str, Any]
    function: Callable[..., str]
    # If True, the UI must ask the user before calling this tool.
    requires_confirmation: bool = False


# Global registry. Populated by @tool decorator.
_REGISTRY: dict[str, Tool] = {}


def tool(
    name: str,
    description: str,
    input_schema: dict[str, Any],
    requires_confirmation: bool = False,
) -> Callable[[Callable[..., str]], Callable[..., str]]:
    """Decorator to register a function as an agent tool."""

    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        _REGISTRY[name] = Tool(
            name=name,
            description=description,
            input_schema=input_schema,
            function=fn,
            requires_confirmation=requires_confirmation,
        )
        return fn

    return decorator


def all_tools() -> list[Tool]:
    """Return all registered tools."""
    return list(_REGISTRY.values())


def get_tool(name: str) -> Tool | None:
    """Look up a tool by name."""
    return _REGISTRY.get(name)


def tools_for_claude() -> list[dict[str, Any]]:
    """Format tool definitions for Claude's Messages API."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in _REGISTRY.values()
    ]


@dataclass
class ToolResult:
    """Result of executing a tool."""

    content: str
    is_error: bool = False


@dataclass
class ToolCallPreview:
    """What a tool wants to do — used to ask the user for confirmation."""

    tool_name: str
    tool_args: dict[str, Any]
    preview_lines: list[str] = field(default_factory=list)
