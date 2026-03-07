"""Report generation logic for the VaultX agent."""

import json
from datetime import datetime, timezone
from typing import Any

from .prompts import REPORT_PROMPT_TEMPLATE


def build_report_prompt(diagnostics: dict[str, Any]) -> str:
    """Return the LLM prompt used to generate a Markdown report."""
    raw_json = json.dumps(diagnostics, indent=2)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return REPORT_PROMPT_TEMPLATE.format(timestamp=timestamp, raw_json=raw_json)


def generate_report(llm_client, diagnostics: dict[str, Any]) -> str:
    """Generate a Markdown diagnostic report using the LLM.

    Parameters
    ----------
    llm_client:
        An :class:`agent.llm.OllamaClient` instance.
    diagnostics:
        Parsed JSON dict returned by :func:`agent.tools.collect_diagnostics`.

    Returns
    -------
    str
        The Markdown report produced by the LLM.
    """
    prompt = build_report_prompt(diagnostics)
    messages = [
        {"role": "user", "content": prompt},
    ]
    return llm_client.chat(messages, stream=False)


def save_report(report: str, path: str) -> None:
    """Write *report* to *path* on disk."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(f"Report saved to: {path}")
