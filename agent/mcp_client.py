"""MCP client integration for VaultX agent."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

from .tool_registry import ToolDescriptor


class MCPClient:
    """Async MCP client wrapper with lifecycle management."""

    def __init__(
        self,
        server_command: list[str] | None = None,
        server_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.server_command = server_command or ["vault-mcp-server"]
        self.server_url = server_url
        self.timeout = timeout
        self._session = None
        self._session_cm = None
        self._transport_cm = None
        self._mcp = None
        self._cached_tools: list[ToolDescriptor] | None = None

    async def __aenter__(self) -> "MCPClient":
        self._mcp = _import_mcp_modules()
        self._transport_cm = self._create_transport()
        read_stream, write_stream = await self._transport_cm.__aenter__()
        self._session_cm = self._mcp.ClientSession(
            read_stream,
            write_stream,
            read_timeout_seconds=self.timeout,
        )

        try:
            self._session = await self._session_cm.__aenter__()
            await self._session.initialize()
            return self
        except Exception:
            await self.__aexit__(None, None, None)
            raise

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if self._session_cm is not None:
            await self._session_cm.__aexit__(exc_type, exc, tb)
            self._session_cm = None
            self._session = None
        if self._transport_cm is not None:
            await self._transport_cm.__aexit__(exc_type, exc, tb)
            self._transport_cm = None
        return False

    async def list_tools(self) -> list[ToolDescriptor]:
        """List available MCP tools."""
        if self._cached_tools is not None:
            return self._cached_tools

        session = self._require_session()
        result = await session.list_tools()
        descriptors: list[ToolDescriptor] = []
        for tool in result.tools:
            name = getattr(tool, "name")
            description = getattr(tool, "description", "") or ""
            parameters = (
                getattr(tool, "inputSchema", None)
                or getattr(tool, "input_schema", None)
                or {"type": "object", "properties": {}, "additionalProperties": False}
            )

            async def _invoke(
                arguments: dict[str, Any] | None = None,
                *,
                tool_name: str = name,
            ) -> Any:
                return await self.call_tool(tool_name, arguments or {})

            descriptors.append(
                ToolDescriptor(
                    name=name,
                    description=description,
                    parameters=parameters,
                    source="mcp",
                    invoke=_invoke,
                )
            )

        self._cached_tools = descriptors
        return descriptors

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool and return a JSON-serializable result."""
        session = self._require_session()
        result = await session.call_tool(
            name=name,
            arguments=arguments or {},
            read_timeout_seconds=self.timeout,
        )
        return _serialize_call_tool_result(result)

    def _create_transport(self):
        if self.server_url:
            if _looks_like_sse_endpoint(self.server_url):
                return self._mcp.sse_client(
                    self.server_url,
                    timeout=self.timeout,
                    sse_read_timeout=max(self.timeout, 300.0),
                )
            if self._mcp.streamable_http_client is None:
                return self._mcp.sse_client(
                    self.server_url,
                    timeout=self.timeout,
                    sse_read_timeout=max(self.timeout, 300.0),
                )
            return self._mcp.streamable_http_client(self.server_url)

        params = self._mcp.StdioServerParameters(
            command=self.server_command[0],
            args=self.server_command[1:],
            env=_build_mcp_child_env(),
        )
        return self._mcp.stdio_client(params)

    def _require_session(self):
        if self._session is None:
            raise RuntimeError("MCP client is not connected.")
        return self._session


def _import_mcp_modules():
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
        from mcp.client.stdio import StdioServerParameters, stdio_client
        try:
            from mcp.client.streamable_http import streamable_http_client
        except ImportError:
            streamable_http_client = None
    except ImportError as exc:
        raise RuntimeError(
            "MCP support requires the 'mcp' package. "
            "Install it with: pip install -r agent/requirements.txt"
        ) from exc

    return SimpleNamespace(
        ClientSession=ClientSession,
        StdioServerParameters=StdioServerParameters,
        stdio_client=stdio_client,
        sse_client=sse_client,
        streamable_http_client=streamable_http_client,
    )


def _build_mcp_child_env() -> dict[str, str]:
    passthrough_prefixes = (
        "VAULT_",
        "SSL_",
        "REQUESTS_",
    )
    passthrough_names = {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "CURL_CA_BUNDLE",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
    }

    def _should_passthrough(name: str) -> bool:
        return name in passthrough_names or name.startswith(passthrough_prefixes)

    return {
        key: value
        for key, value in os.environ.items()
        if _should_passthrough(key)
    }


def _looks_like_sse_endpoint(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith("/sse") or path.endswith("/events")


def _serialize_call_tool_result(result: Any) -> Any:
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured

    content = getattr(result, "content", None) or []
    if not content:
        return {"is_error": getattr(result, "is_error", False), "content": []}

    rendered_content: list[Any] = []
    for item in content:
        text = getattr(item, "text", None)
        if text is not None:
            rendered_content.append(text)
            continue
        if hasattr(item, "model_dump"):
            rendered_content.append(item.model_dump(by_alias=True, mode="json", exclude_none=True))
            continue
        rendered_content.append(item)

    if len(rendered_content) == 1:
        return rendered_content[0]

    return {
        "is_error": getattr(result, "is_error", False),
        "content": rendered_content,
    }
