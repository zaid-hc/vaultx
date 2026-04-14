"""Tool definitions that wrap the vaultx bash script."""

import json
import os
import shutil
import subprocess
import sys
from typing import Any

from .tool_registry import ToolDescriptor


def _find_vaultx() -> str:
    """Return the path to the vaultx script.

    Search order:
    1. ``VAULTX_PATH`` environment variable
    2. A ``vaultx`` file next to this package (i.e. repo root)
    3. ``vaultx`` on PATH
    """
    env_path = os.environ.get("VAULTX_PATH")
    if env_path:
        if os.path.isfile(env_path) and os.access(env_path, os.X_OK):
            return env_path
        print(
            f"Warning: VAULTX_PATH='{env_path}' is not an executable file. "
            "Falling back to auto-detection.",
            file=sys.stderr,
        )

    # Resolve relative to this file: agent/ is one level below repo root.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(repo_root, "vaultx")
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate

    which = shutil.which("vaultx")
    if which:
        return which

    print(
        "Error: 'vaultx' script not found.\n"
        "Ensure that:\n"
        "  - The 'vaultx' script is in the same directory as the 'agent/' package, or\n"
        "  - 'vaultx' is on your PATH, or\n"
        "  - The VAULTX_PATH environment variable points to the script.",
        file=sys.stderr,
    )
    sys.exit(1)


def collect_diagnostics() -> dict[str, Any]:
    """Run ``vaultx -format=json`` and return the parsed JSON output.

    Returns an empty dict if the script fails or produces no JSON.
    """
    vaultx = _find_vaultx()
    try:
        result = subprocess.run(
            [vaultx, "-format=json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        print(f"Error: vaultx not found at '{vaultx}'.", file=sys.stderr)
        return {}
    except subprocess.TimeoutExpired:
        print("Error: vaultx timed out after 120 seconds.", file=sys.stderr)
        return {}
    except Exception as exc:  # noqa: BLE001
        print(f"Error running vaultx: {exc}", file=sys.stderr)
        return {}

    output = result.stdout.strip()
    if not output:
        if result.returncode != 0:
            print(
                f"Warning: vaultx exited with code {result.returncode}.\n"
                f"Stderr: {result.stderr.strip()}",
                file=sys.stderr,
            )
        else:
            print("Warning: vaultx produced no output.", file=sys.stderr)
        return {}

    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        if result.returncode != 0:
            print(
                f"Warning: vaultx exited with code {result.returncode}.\n"
                f"Stderr: {result.stderr.strip()}",
                file=sys.stderr,
            )
        print(f"Error: Could not parse vaultx JSON output: {exc}", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# Convenience extractors
# ---------------------------------------------------------------------------

def get_node_status(diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the node_status section from diagnostics."""
    data = diagnostics if diagnostics is not None else collect_diagnostics()
    return data.get("node_status", {})


def get_raft_peers(diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the raft_peers section from diagnostics."""
    data = diagnostics if diagnostics is not None else collect_diagnostics()
    return data.get("raft_peers", {})


def get_license_info(diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the license section from diagnostics."""
    data = diagnostics if diagnostics is not None else collect_diagnostics()
    return data.get("license", {})


def get_replication_status(diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the replication section from diagnostics."""
    data = diagnostics if diagnostics is not None else collect_diagnostics()
    return data.get("replication", {})


def get_audit_devices(diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the audit_devices section from diagnostics."""
    data = diagnostics if diagnostics is not None else collect_diagnostics()
    return data.get("audit_devices", {})


def get_autopilot_state(diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the autopilot_state section from diagnostics."""
    data = diagnostics if diagnostics is not None else collect_diagnostics()
    return data.get("autopilot_state", {})


def get_autopilot_config(diagnostics: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the autopilot_config section from diagnostics."""
    data = diagnostics if diagnostics is not None else collect_diagnostics()
    return data.get("autopilot_config", {})


class DiagnosticsContext:
    """Mutable holder for a cached diagnostics snapshot."""

    def __init__(self, diagnostics: dict[str, Any] | None = None) -> None:
        self.diagnostics = diagnostics

    def get(self) -> dict[str, Any] | None:
        """Return the cached snapshot."""
        return self.diagnostics

    def set(self, diagnostics: dict[str, Any] | None) -> None:
        """Replace the cached snapshot."""
        self.diagnostics = diagnostics

    def refresh(self) -> dict[str, Any]:
        """Collect a fresh diagnostics snapshot."""
        self.diagnostics = collect_diagnostics()
        return self.diagnostics

    def ensure(self) -> dict[str, Any]:
        """Return a snapshot, collecting one on demand if needed."""
        if self.diagnostics is None:
            self.refresh()
        return self.diagnostics or {}


def get_local_tool_descriptors(context: DiagnosticsContext) -> list[ToolDescriptor]:
    """Return local diagnostics tools compatible with the unified registry."""
    empty_parameters = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    async def _collect(_: dict[str, Any] | None = None) -> dict[str, Any]:
        return context.refresh()

    async def _node_status(_: dict[str, Any] | None = None) -> dict[str, Any]:
        return get_node_status(context.ensure())

    async def _raft_peers(_: dict[str, Any] | None = None) -> dict[str, Any]:
        return get_raft_peers(context.ensure())

    async def _license(_: dict[str, Any] | None = None) -> dict[str, Any]:
        return get_license_info(context.ensure())

    async def _replication(_: dict[str, Any] | None = None) -> dict[str, Any]:
        return get_replication_status(context.ensure())

    async def _audit_devices(_: dict[str, Any] | None = None) -> dict[str, Any]:
        return get_audit_devices(context.ensure())

    async def _autopilot_state(_: dict[str, Any] | None = None) -> dict[str, Any]:
        return get_autopilot_state(context.ensure())

    async def _autopilot_config(_: dict[str, Any] | None = None) -> dict[str, Any]:
        return get_autopilot_config(context.ensure())

    return [
        ToolDescriptor(
            name="vaultx_collect_diagnostics",
            description="Refresh the cached VaultX diagnostics snapshot from the local vaultx CLI.",
            parameters=empty_parameters,
            source="local",
            invoke=_collect,
        ),
        ToolDescriptor(
            name="vaultx_get_node_status",
            description="Get the current node status section from the cached VaultX diagnostics snapshot.",
            parameters=empty_parameters,
            source="local",
            invoke=_node_status,
        ),
        ToolDescriptor(
            name="vaultx_get_raft_peers",
            description="Get the current raft peers section from the cached VaultX diagnostics snapshot.",
            parameters=empty_parameters,
            source="local",
            invoke=_raft_peers,
        ),
        ToolDescriptor(
            name="vaultx_get_license_info",
            description="Get the current license section from the cached VaultX diagnostics snapshot.",
            parameters=empty_parameters,
            source="local",
            invoke=_license,
        ),
        ToolDescriptor(
            name="vaultx_get_replication_status",
            description="Get the current replication section from the cached VaultX diagnostics snapshot.",
            parameters=empty_parameters,
            source="local",
            invoke=_replication,
        ),
        ToolDescriptor(
            name="vaultx_get_audit_devices",
            description="Get the current audit devices section from the cached VaultX diagnostics snapshot.",
            parameters=empty_parameters,
            source="local",
            invoke=_audit_devices,
        ),
        ToolDescriptor(
            name="vaultx_get_autopilot_state",
            description="Get the current autopilot state section from the cached VaultX diagnostics snapshot.",
            parameters=empty_parameters,
            source="local",
            invoke=_autopilot_state,
        ),
        ToolDescriptor(
            name="vaultx_get_autopilot_config",
            description="Get the current autopilot configuration section from the cached VaultX diagnostics snapshot.",
            parameters=empty_parameters,
            source="local",
            invoke=_autopilot_config,
        ),
    ]
