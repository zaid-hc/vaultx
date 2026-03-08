"""Tool definitions that wrap the vaultx bash script."""

import json
import os
import shutil
import subprocess
import sys
from typing import Any


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
