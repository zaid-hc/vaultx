"""CLI entry point for the VaultX AI agent."""

import asyncio
import argparse
import json
import sys
from typing import Any

from .config import AgentConfig
from .llm import OllamaClient
from .mcp_client import MCPClient
from .prompts import (
    INTERACTIVE_CONTEXT_TEMPLATE,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_WITH_MCP,
    TOOL_CALL_RESULT_TEMPLATE,
)
from .report import build_report_prompt, generate_report, save_report
from .tool_registry import ToolRegistry
from .tools import DiagnosticsContext, get_local_tool_descriptors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vaultx-agent",
        description=(
            "VaultX AI Agent — conversational diagnostics and report generation "
            "for HashiCorp Vault clusters powered by a local LLM via Ollama."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  vaultx-agent                          # Interactive mode
  vaultx-agent --generate-report        # Generate a support ticket report
  vaultx-agent -r -o report.md          # Generate report and save to file
  vaultx-agent --model llama3.2:3b      # Use a different model
        """,
    )
    parser.add_argument(
        "--generate-report",
        "-r",
        action="store_true",
        default=False,
        help="Collect all diagnostics and generate a comprehensive support ticket report.",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL",
        default="llama3.1:8b",
        help="Ollama model to use (default: llama3.1:8b).",
    )
    parser.add_argument(
        "--ollama-host",
        metavar="HOST",
        default="http://localhost:11434",
        help="Ollama server URL (default: http://localhost:11434).",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        default=None,
        help="Save report output to FILE (only used with --generate-report).",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        default=False,
        help="Enable MCP support and connect to vault-mcp-server.",
    )
    parser.add_argument(
        "--mcp-server-command",
        metavar="CMD",
        default=None,
        help='Command used to launch the MCP server over stdio (default: "vault-mcp-server").',
    )
    parser.add_argument(
        "--mcp-server-url",
        metavar="URL",
        default=None,
        help="Connect to a running MCP server over Streamable HTTP or SSE instead of starting one locally.",
    )
    parser.add_argument(
        "--mcp-timeout",
        metavar="SECS",
        type=float,
        default=30.0,
        help="Seconds to wait for MCP requests (default: 30).",
    )
    return parser


async def _run_interactive(
    llm: OllamaClient,
    tool_registry: ToolRegistry,
    diagnostics_context: DiagnosticsContext,
) -> None:
    """Start an interactive conversational session."""
    print("VaultX AI Agent — Interactive Mode")
    print("Type your question about the Vault cluster (or 'quit' / Ctrl-C to exit).")
    print("Type 'refresh' to re-collect diagnostic data.\n")

    system_prompt = SYSTEM_PROMPT_WITH_MCP if tool_registry.has_mcp_tools() else SYSTEM_PROMPT
    conversation: list[dict] = [{"role": "system", "content": system_prompt}]

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        if user_input.lower() == "refresh":
            print("Re-collecting diagnostics …")
            diagnostics = diagnostics_context.refresh()
            if diagnostics:
                print("Diagnostics refreshed.\n")
            else:
                print("Warning: Could not collect diagnostics.\n")
            continue

        # Lazy-load diagnostics on first question
        diagnostics = diagnostics_context.get()
        if diagnostics is None:
            print("Collecting diagnostics …")
            diagnostics = diagnostics_context.refresh()
            if not diagnostics:
                print(
                    "Warning: Could not collect diagnostics. "
                    "Ensure VAULT_ADDR and VAULT_TOKEN are set.\n"
                )

        # Attach current diagnostic context to the user message
        if diagnostics:
            user_message = INTERACTIVE_CONTEXT_TEMPLATE.format(
                diagnostics_json=json.dumps(diagnostics, indent=2),
                mcp_tools_available=_mcp_availability_message(tool_registry),
                user_question=user_input,
            )
        else:
            user_message = user_input

        conversation.append({"role": "user", "content": user_message})

        print("Agent: ", end="", flush=True)
        full_response = await _complete_with_tools(llm, conversation, tool_registry, stream=True)
        print(full_response)
        conversation.append({"role": "assistant", "content": full_response})


async def _run_report(
    llm: OllamaClient,
    output_file: str | None,
    tool_registry: ToolRegistry,
    diagnostics_context: DiagnosticsContext,
) -> None:
    """Collect diagnostics and generate a Markdown report."""
    print("Collecting diagnostics from Vault cluster …")
    diagnostics = diagnostics_context.refresh()

    if not diagnostics:
        print(
            "Error: No diagnostic data collected. "
            "Ensure VAULT_ADDR and VAULT_TOKEN are set and the Vault cluster is reachable.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Generating report with model '{llm.model}' …")
    if tool_registry.has_mcp_tools():
        report_prompt = build_report_prompt(diagnostics)
        report = await _complete_with_tools(
            llm,
            [{"role": "system", "content": SYSTEM_PROMPT_WITH_MCP}, {"role": "user", "content": report_prompt}],
            tool_registry,
            stream=False,
        )
    else:
        report = generate_report(llm, diagnostics)

    if output_file:
        save_report(report, output_file)
    else:
        print("\n" + report)


def main(argv: list[str] | None = None) -> None:
    asyncio.run(_async_main(argv))


async def _async_main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = AgentConfig.from_args(args)

    if config.mcp_enabled and config.mcp_server_command_explicit and config.mcp_server_url:
        parser.error("Use either --mcp-server-command or --mcp-server-url, not both.")

    llm = OllamaClient(model=config.model, host=config.ollama_host)
    llm.check_availability()

    diagnostics_context = DiagnosticsContext()
    local_tools = get_local_tool_descriptors(diagnostics_context)

    if config.mcp_enabled:
        async with MCPClient(
            server_command=config.mcp_command_parts(),
            server_url=config.mcp_server_url,
            timeout=config.mcp_timeout,
        ) as mcp_client:
            tool_registry = await ToolRegistry.create(local_tools=local_tools, mcp_client=mcp_client)
            if config.generate_report:
                await _run_report(llm, config.output, tool_registry, diagnostics_context)
            else:
                await _run_interactive(llm, tool_registry, diagnostics_context)
        return

    tool_registry = ToolRegistry(local_tools=local_tools)
    if config.generate_report:
        await _run_report(llm, config.output, tool_registry, diagnostics_context)
    else:
        await _run_interactive(llm, tool_registry, diagnostics_context)


async def _complete_with_tools(
    llm: OllamaClient,
    conversation: list[dict[str, Any]],
    tool_registry: ToolRegistry,
    stream: bool = False,
    max_round_trips: int = 6,
) -> str:
    if not tool_registry.has_tools():
        if stream:
            return "".join(llm.chat(conversation, stream=True))
        return llm.chat(conversation, stream=False)

    working_conversation = list(conversation)
    tools = tool_registry.to_ollama_tool_defs()

    for _ in range(max_round_trips):
        response_text, tool_calls = llm.chat_with_tools(working_conversation, tools, stream=False)
        if response_text:
            working_conversation.append({"role": "assistant", "content": response_text})

        if not tool_calls:
            return response_text or ""

        for tool_call in tool_calls:
            tool_result = await tool_registry.invoke(tool_call.name, tool_call.arguments)
            working_conversation.append(
                {
                    "role": "user",
                    "content": TOOL_CALL_RESULT_TEMPLATE.format(
                        tool_name=tool_call.name,
                        result_json=_format_tool_result(tool_result),
                    )
                    + "\nUse this tool output to continue helping the user.",
                }
            )

    return (
        f"Unable to complete the request after {max_round_trips} tool invocations. "
        "The model may be stuck in a loop or encountering repeated tool failures."
    )


def _format_tool_result(tool_result: Any) -> str:
    if isinstance(tool_result, str):
        return json.dumps(tool_result)
    return json.dumps(tool_result, indent=2, sort_keys=True)


def _mcp_availability_message(tool_registry: ToolRegistry) -> str:
    if tool_registry.has_mcp_tools():
        return "MCP tools are available for live Vault API operations when the cached diagnostics snapshot is not enough."
    return "No MCP tools are configured; answer from the cached VaultX diagnostics snapshot."


if __name__ == "__main__":
    main()
