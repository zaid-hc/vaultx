"""Configuration helpers for the VaultX agent."""

from __future__ import annotations

from dataclasses import dataclass
import os
import shlex


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class AgentConfig:
    """Runtime configuration for the VaultX agent."""

    generate_report: bool = False
    model: str = "llama3.1:8b"
    ollama_host: str = "http://localhost:11434"
    output: str | None = None
    mcp_enabled: bool = False
    mcp_server_command: str = "vault-mcp-server"
    mcp_server_command_explicit: bool = False
    mcp_server_url: str | None = None
    mcp_timeout: float = 30.0

    @classmethod
    def from_args(cls, args) -> "AgentConfig":
        """Build configuration from parsed CLI arguments and environment."""
        env_command = os.environ.get("VAULTX_MCP_SERVER_COMMAND")
        return cls(
            generate_report=args.generate_report,
            model=args.model,
            ollama_host=args.ollama_host,
            output=args.output,
            mcp_enabled=args.mcp or _env_flag("VAULTX_MCP"),
            mcp_server_command=args.mcp_server_command or env_command or "vault-mcp-server",
            mcp_server_command_explicit=args.mcp_server_command is not None or env_command is not None,
            mcp_server_url=args.mcp_server_url or os.environ.get("VAULTX_MCP_SERVER_URL"),
            mcp_timeout=float(args.mcp_timeout),
        )

    def mcp_command_parts(self) -> list[str]:
        """Return the configured MCP server command split into argv parts."""
        parts = shlex.split(self.mcp_server_command)
        if not parts:
            raise ValueError("MCP server command must not be empty.")
        return parts
