"""Ollama LLM client wrapper for the VaultX agent."""

import sys


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
        return response.message.content

    def _stream_chat(self, messages: list[dict]):
        """Yield text chunks from a streaming chat response."""
        for chunk in self._client.chat(model=self.model, messages=messages, stream=True):
            content = chunk.message.content
            if content:
                yield content
