"""Unit tests for VaultX agent MCP integration."""

from __future__ import annotations

import argparse
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from agent import cli
from agent.config import AgentConfig
from agent.llm import OllamaClient, ToolCall
from agent.mcp_client import MCPClient
from agent.tool_registry import ToolDescriptor, ToolRegistry
from agent.tools import DiagnosticsContext, get_local_tool_descriptors


class AgentConfigTests(unittest.TestCase):
    def test_from_args_uses_environment_fallbacks(self) -> None:
        args = argparse.Namespace(
            generate_report=False,
            model="llama3.1:8b",
            ollama_host="http://localhost:11434",
            output=None,
            mcp=False,
            mcp_server_command=None,
            mcp_server_url=None,
            mcp_timeout=45,
        )

        with patch.dict(
            os.environ,
            {
                "VAULTX_MCP": "true",
                "VAULTX_MCP_SERVER_COMMAND": "vault-mcp-server --stdio",
                "VAULTX_MCP_SERVER_URL": "http://127.0.0.1:8080/mcp",
            },
            clear=False,
        ):
            config = AgentConfig.from_args(args)

        self.assertTrue(config.mcp_enabled)
        self.assertEqual(config.mcp_server_command, "vault-mcp-server --stdio")
        self.assertEqual(config.mcp_server_url, "http://127.0.0.1:8080/mcp")
        self.assertEqual(config.mcp_timeout, 45.0)

    def test_mcp_command_parts_splits_shell_words(self) -> None:
        config = AgentConfig(mcp_server_command="uvx vault-mcp-server --transport stdio")
        self.assertEqual(
            config.mcp_command_parts(),
            ["uvx", "vault-mcp-server", "--transport", "stdio"],
        )


class ToolRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_registry_merges_tools_and_invokes_by_name(self) -> None:
        local_tool = ToolDescriptor(
            name="vaultx_get_node_status",
            description="Get node status",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            source="local",
            invoke=AsyncMock(return_value={"sealed": False}),
        )
        mcp_tool = ToolDescriptor(
            name="vault_read_secret",
            description="Read secret",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            source="mcp",
            invoke=AsyncMock(return_value={"data": {"key": "value"}}),
        )

        registry = ToolRegistry(local_tools=[local_tool], mcp_tools=[mcp_tool])

        self.assertTrue(registry.has_tools())
        self.assertTrue(registry.has_mcp_tools())
        self.assertEqual(len(registry.all_tools()), 2)
        self.assertEqual(
            registry.to_ollama_tool_defs()[0]["function"]["name"],
            "vaultx_get_node_status",
        )
        self.assertEqual(
            await registry.invoke("vault_read_secret", {"path": "kv/app"}),
            {"data": {"key": "value"}},
        )


class DiagnosticsToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_tool_descriptors_use_cached_snapshot(self) -> None:
        context = DiagnosticsContext({"node_status": {"node-a": {"sealed": False}}})
        registry = ToolRegistry(local_tools=get_local_tool_descriptors(context))

        result = await registry.invoke("vaultx_get_node_status")

        self.assertEqual(result, {"node-a": {"sealed": False}})

    async def test_refresh_tool_recollects_diagnostics(self) -> None:
        context = DiagnosticsContext()
        registry = ToolRegistry(local_tools=get_local_tool_descriptors(context))

        with patch("agent.tools.collect_diagnostics", return_value={"license": {"days_remaining": 7}}):
            result = await registry.invoke("vaultx_collect_diagnostics")

        self.assertEqual(result, {"license": {"days_remaining": 7}})
        self.assertEqual(context.get(), {"license": {"days_remaining": 7}})


class OllamaClientToolTests(unittest.TestCase):
    def test_chat_with_tools_parses_tool_calls(self) -> None:
        client = OllamaClient.__new__(OllamaClient)
        client.model = "llama3.1:8b"
        client._client = SimpleNamespace(
            chat=MagicMock(
                return_value=SimpleNamespace(
                    message=SimpleNamespace(
                        content="Let me check that.",
                        tool_calls=[
                            SimpleNamespace(
                                function=SimpleNamespace(
                                    name="vault_read_secret",
                                    arguments='{"path": "kv/app"}',
                                )
                            )
                        ],
                    )
                )
            )
        )

        content, tool_calls = client.chat_with_tools(
            [{"role": "user", "content": "Read kv/app"}],
            [{"type": "function", "function": {"name": "vault_read_secret"}}],
        )

        self.assertEqual(content, "Let me check that.")
        self.assertEqual(tool_calls, [ToolCall(name="vault_read_secret", arguments={"path": "kv/app"})])


class MCPClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_tools_wraps_session_tools(self) -> None:
        client = MCPClient(server_command=["vault-mcp-server"])
        client._session = SimpleNamespace(
            list_tools=AsyncMock(
                return_value=SimpleNamespace(
                    tools=[
                        SimpleNamespace(
                            name="vault_read_secret",
                            description="Read a Vault secret",
                            inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
                        )
                    ]
                )
            )
        )
        client.call_tool = AsyncMock(return_value={"data": {"foo": "bar"}})

        descriptors = await client.list_tools()
        result = await descriptors[0].invoke({"path": "kv/app"})

        self.assertEqual(descriptors[0].source, "mcp")
        self.assertEqual(result, {"data": {"foo": "bar"}})
        client.call_tool.assert_awaited_once_with("vault_read_secret", {"path": "kv/app"})

    async def test_create_transport_uses_stdio_and_filtered_env(self) -> None:
        client = MCPClient(server_command=["vault-mcp-server", "--stdio"])
        captured: dict[str, object] = {}

        def fake_params(**kwargs):
            captured.update(kwargs)
            return kwargs

        fake_stdio = MagicMock(return_value="stdio-transport")
        client._mcp = SimpleNamespace(
            StdioServerParameters=fake_params,
            stdio_client=fake_stdio,
            sse_client=MagicMock(),
            streamable_http_client=MagicMock(),
        )

        with patch.dict(os.environ, {"VAULT_ADDR": "https://vault.service", "UNRELATED": "skip"}, clear=False):
            transport = client._create_transport()

        self.assertEqual(transport, "stdio-transport")
        self.assertEqual(captured["command"], "vault-mcp-server")
        self.assertEqual(captured["args"], ["--stdio"])
        self.assertIn("VAULT_ADDR", captured["env"])
        self.assertEqual(captured["env"]["VAULT_ADDR"], "https://vault.service")
        self.assertNotIn("UNRELATED", captured["env"])


class CLIToolLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_complete_with_tools_loops_until_final_response(self) -> None:
        class FakeLLM:
            def __init__(self) -> None:
                self.calls = 0

            def chat_with_tools(self, messages, tools, stream=False):
                self.calls += 1
                if self.calls == 1:
                    return ("Checking live data.", [ToolCall(name="vault_read_secret", arguments={"path": "kv/app"})])
                self.last_messages = messages
                return ("Done.", [])

            def chat(self, messages, stream=False):
                return "unused"

        registry = ToolRegistry(
            mcp_tools=[
                ToolDescriptor(
                    name="vault_read_secret",
                    description="Read a Vault secret",
                    parameters={
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                    source="mcp",
                    invoke=AsyncMock(return_value={"data": {"token": "redacted"}}),
                )
            ]
        )

        response = await cli._complete_with_tools(
            FakeLLM(),
            [{"role": "user", "content": "Read kv/app"}],
            registry,
        )

        self.assertEqual(response, "Done.")

    def test_parser_accepts_mcp_flags(self) -> None:
        parser = cli._build_parser()

        args = parser.parse_args(
            [
                "--mcp",
                "--mcp-server-command",
                "uvx vault-mcp-server --transport stdio",
                "--mcp-timeout",
                "15",
            ]
        )

        self.assertTrue(args.mcp)
        self.assertEqual(args.mcp_server_command, "uvx vault-mcp-server --transport stdio")
        self.assertEqual(args.mcp_timeout, 15.0)


if __name__ == "__main__":
    unittest.main()
