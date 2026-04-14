"""Ollama LLM client wrapper for the VaultX agent."""

import json
import sys
from dataclasses import dataclass
from typing import Any


def _import_ollama():
    try:
        import ollama  # noqa: PLC0415
        return ollama
    except ImportError:
        print(
            "Error: The 'ollama' Python package is not installed.\n"
            "Install it with: pip install -r agent/requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)


class OllamaClient:
    """Thin wrapper around the Ollama Python client."""

    def __init__(self, model: str = "llama3.1:8b", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host
        self._ollama = _import_ollama()
        self._client = self._ollama.Client(host=host)

    def check_availability(self) -> None:
        """Check that Ollama is running and the requested model is available.

        Raises SystemExit with a helpful message if either check fails.
        """
        try:
            available = self._client.list()
        except Exception as exc:  # noqa: BLE001
            print(
                f"Error: Cannot connect to Ollama at {self.host}\n"
                "Make sure Ollama is installed and running:\n"
                "  https://ollama.com/download\n"
                "  ollama serve\n"
                f"Details: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

        model_names = [m.model for m in available.models]
        # Normalise: strip the ":latest" suffix for comparison
        def _base(name: str) -> str:
            return name.split(":")[0] if ":" in name else name

        requested_base = _base(self.model)
        if not any(_base(m) == requested_base or m == self.model for m in model_names):
            print(
                f"Error: Model '{self.model}' is not available in Ollama.\n"
                f"Pull it with: ollama pull {self.model}\n"
                f"Available models: {', '.join(model_names) or '(none)'}",
                file=sys.stderr,
            )
            sys.exit(1)

    def chat(self, messages: list[dict], stream: bool = False):
        """Send a chat request to Ollama.

        Parameters
        ----------
        messages:
            List of ``{"role": ..., "content": ...}`` dicts.
        stream:
            When *True* yields response chunks; when *False* returns the full
            message content string.
        """
        if stream:
            return self._stream_chat(messages)
        response = self._client.chat(model=self.model, messages=messages)
        return _get_message_content(response)

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        stream: bool = False,
    ) -> tuple[str | None, list["ToolCall"]]:
        """Send a tool-enabled chat request to Ollama."""
        response = self._client.chat(
            model=self.model,
            messages=messages,
            tools=tools,
            stream=stream,
        )
        if stream:
            content_parts: list[str] = []
            tool_calls: list[ToolCall] = []
            for chunk in response:
                chunk_content = _get_message_content(chunk)
                if chunk_content:
                    content_parts.append(chunk_content)
                tool_calls.extend(_extract_tool_calls(chunk))
            return ("".join(content_parts) or None, tool_calls)
        return (_get_message_content(response), _extract_tool_calls(response))

    def _stream_chat(self, messages: list[dict]):
        """Yield text chunks from a streaming chat response."""
        for chunk in self._client.chat(model=self.model, messages=messages, stream=True):
            content = _get_message_content(chunk)
            if content:
                yield content


@dataclass(slots=True)
class ToolCall:
    """Structured representation of an LLM-requested tool call."""

    name: str
    arguments: dict[str, Any]


def _get_message(response: Any) -> Any:
    if isinstance(response, dict):
        return response.get("message", {})
    return getattr(response, "message", {})


def _get_message_content(response: Any) -> str | None:
    message = _get_message(response)
    if isinstance(message, dict):
        return message.get("content")
    return getattr(message, "content", None)


def _extract_tool_calls(response: Any) -> list[ToolCall]:
    message = _get_message(response)
    raw_tool_calls = message.get("tool_calls", []) if isinstance(message, dict) else getattr(message, "tool_calls", [])
    parsed_calls: list[ToolCall] = []
    for raw_call in raw_tool_calls or []:
        function = raw_call.get("function", {}) if isinstance(raw_call, dict) else getattr(raw_call, "function", None)
        if function is None:
            continue
        name = function.get("name") if isinstance(function, dict) else getattr(function, "name", None)
        arguments = (
            function.get("arguments", {})
            if isinstance(function, dict)
            else getattr(function, "arguments", {})
        )
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        parsed_calls.append(ToolCall(name=name or "", arguments=arguments or {}))
    return [call for call in parsed_calls if call.name]
