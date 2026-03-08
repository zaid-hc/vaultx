"""CLI entry point for the VaultX AI agent."""

import argparse
import json
import sys
from typing import Any

from .llm import OllamaClient
from .prompts import INTERACTIVE_CONTEXT_TEMPLATE, SYSTEM_PROMPT
from .report import generate_report, save_report
from .tools import collect_diagnostics


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
    return parser


def _run_interactive(llm: OllamaClient) -> None:
    """Start an interactive conversational session."""
    print("VaultX AI Agent — Interactive Mode")
    print("Type your question about the Vault cluster (or 'quit' / Ctrl-C to exit).")
    print("Type 'refresh' to re-collect diagnostic data.\n")

    diagnostics: dict[str, Any] | None = None
    conversation: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

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
            diagnostics = collect_diagnostics()
            if diagnostics:
                print("Diagnostics refreshed.\n")
            else:
                print("Warning: Could not collect diagnostics.\n")
            continue

        # Lazy-load diagnostics on first question
        if diagnostics is None:
            print("Collecting diagnostics …")
            diagnostics = collect_diagnostics()
            if not diagnostics:
                print(
                    "Warning: Could not collect diagnostics. "
                    "Ensure VAULT_ADDR and VAULT_TOKEN are set.\n"
                )

        # Attach current diagnostic context to the user message
        if diagnostics:
            user_message = INTERACTIVE_CONTEXT_TEMPLATE.format(
                diagnostics_json=json.dumps(diagnostics, indent=2),
                user_question=user_input,
            )
        else:
            user_message = user_input

        conversation.append({"role": "user", "content": user_message})

        print("Agent: ", end="", flush=True)
        response_parts: list[str] = []
        for chunk in llm.chat(conversation, stream=True):
            print(chunk, end="", flush=True)
            response_parts.append(chunk)
        print()  # newline after streamed response

        full_response = "".join(response_parts)
        conversation.append({"role": "assistant", "content": full_response})


def _run_report(llm: OllamaClient, output_file: str | None) -> None:
    """Collect diagnostics and generate a Markdown report."""
    print("Collecting diagnostics from Vault cluster …")
    diagnostics = collect_diagnostics()

    if not diagnostics:
        print(
            "Error: No diagnostic data collected. "
            "Ensure VAULT_ADDR and VAULT_TOKEN are set and the Vault cluster is reachable.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Generating report with model '{llm.model}' …")
    report = generate_report(llm, diagnostics)

    if output_file:
        save_report(report, output_file)
    else:
        print("\n" + report)


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    llm = OllamaClient(model=args.model, host=args.ollama_host)
    llm.check_availability()

    if args.generate_report:
        _run_report(llm, args.output)
    else:
        _run_interactive(llm)


if __name__ == "__main__":
    main()
