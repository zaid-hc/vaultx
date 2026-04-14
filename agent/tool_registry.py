"""Unified tool registry for local VaultX and MCP-backed tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(slots=True)
class ToolDescriptor:
    """Description of a callable tool exposed to the LLM."""

    name: str
    description: str
    parameters: dict[str, Any]
    source: Literal["local", "mcp"]
    invoke: Callable[[dict[str, Any] | None], Awaitable[Any]]


class ToolRegistry:
    """Holds all tool descriptors available to the agent."""

    def __init__(
        self,
        local_tools: Iterable[ToolDescriptor] | None = None,
        mcp_tools: Iterable[ToolDescriptor] | None = None,
    ) -> None:
        tools = [*(local_tools or []), *(mcp_tools or [])]
        names = [tool.name for tool in tools]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"Duplicate tool names found: {', '.join(duplicates)}")
        self._tools = {tool.name: tool for tool in tools}

    @classmethod
    async def create(
        cls,
        local_tools: Iterable[ToolDescriptor] | None = None,
        mcp_client=None,
    ) -> "ToolRegistry":
        """Build a registry from local tools plus optional MCP tools."""
        mcp_tools = await mcp_client.list_tools() if mcp_client else []
        return cls(local_tools=local_tools, mcp_tools=mcp_tools)

    def all_tools(self) -> list[ToolDescriptor]:
        """Return all registered tools."""
        return list(self._tools.values())

    def has_tools(self) -> bool:
        """Return True when any tool is registered."""
        return bool(self._tools)

    def has_mcp_tools(self) -> bool:
        """Return True when one or more MCP tools are registered."""
        return any(tool.source == "mcp" for tool in self._tools.values())

    def to_ollama_tool_defs(self) -> list[dict[str, Any]]:
        """Return Ollama-compatible function tool definitions."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    async def invoke(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Invoke a tool by name."""
        try:
            tool = self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc
        return await tool.invoke(arguments or {})
