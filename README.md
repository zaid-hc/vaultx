# VaultX

VaultX is a diagnostic and reporting tool for HashiCorp Vault clusters. It helps operators quickly collect health, topology, configuration, and operational details for troubleshooting, validation, and environment review. In version 1.2, VaultX adds a sanitize option that redacts sensitive configuration data so reports and config samples are safer to share with teammates, support, and incident responders.

## Overview

VaultX is a bash-based CLI tool designed to streamline Vault cluster diagnostics and troubleshooting. It gathers critical information about your Vault deployment including node status, Raft configuration, license details, replication status, and more - making it useful for debugging cluster issues, reviewing environment state, and preparing support data.

## Features

- 🔍 **Comprehensive Diagnostics**: Collects essential Vault cluster information in one command
- 🎨 **Colorized Output**: Easy-to-read CLI output with color-coded status indicators
- 📊 **Pretty-Printed JSON**: Export diagnostic data in formatted JSON
- ⚡ **Parallel Data Collection**: Fast data gathering using parallel execution
- 🔐 **Secure Authentication**: Supports `VAULT_TOKEN` environment variable or interactive token input
- 🛡️ **Config Sanitization**: Redact or mask sensitive values from Vault config files before sharing

## What VaultX Collects

- **Node Status**: Health and status of all cluster nodes
- **Raft Peers**: Raft consensus member information
- **Operator Members**: Cluster member details including versions and roles
- **License Information**: License expiration and feature flags
- **Autopilot State**: Automated upgrade and health management status
- **Autopilot Config**: Autopilot configuration parameters
- **Replication Status**: DR and Performance replication health
- **Audit Devices**: Configured audit backends

## Prerequisites

VaultX requires the following tools to be installed:

- `vault` - HashiCorp Vault CLI
- `jq` - JSON processor for parsing and pretty-printing
- `bash` - Version 4.0 or higher recommended

## Installation

1. Download the `vaultx` script:
```bash
curl -O https://raw.githubusercontent.com/zaid-hc/vaultx/main/vaultx
```

2. Make it executable:
```bash
chmod +x vaultx
```

3. (Optional) Move to a directory in your PATH:
```bash
sudo mv vaultx /usr/local/bin/
```

## Usage

### Basic Usage

Run with colorized CLI output:
```bash
vaultx
```

### JSON Output

Output diagnostics in pretty-printed JSON format:
```bash
vaultx -format=json
```

### Export to File

Export diagnostic data to a file (automatically pretty-printed):
```bash
vaultx -export=diagnostics.json
```

### Help

Display help message:
```bash
vaultx -help
```

## Config Sanitization

Use `vaultx sanitize` to redact or mask sensitive values from a Vault config file before sharing it with support teams or collaborators. No Vault connection or token is required for this subcommand.

### Basic Usage

```bash
# Print sanitized config to stdout
vaultx sanitize -config=config.hcl

# Positional form (equivalent)
vaultx sanitize config.hcl

# Write sanitized output to a file
vaultx sanitize -config=config.hcl -out=sanitized.hcl
```

### Sanitization Policy Matrix

All config keys fall into one of four named categories. Keys not explicitly listed are handled by the **generic fallback** (see below).

| Category | Treatment | Named keys (case-insensitive) |
|---|---|---|
| **secret / full-redact** | Replaced with `***REDACTED***` | `token`, `auth_token`, `api_key`, `secret`, `client_secret`, `kms_key`, `kms_key_id`, `private_key`, `password`, `access_key`, `secret_key` |
| **endpoint / anonymize** | Host anonymized; scheme, port, path preserved | `vault_addr`, `api_addr`, `cluster_addr`, `cluster_address`, `address`, `redirect_addr` |
| **path / tail-preserve** | Leading directories replaced with `...`; last two path segments kept | `path`, `tls_cert_file`, `tls_key_file`, `tls_client_ca_file`, `tls_ca_file`, `ca_cert`, `ca_path`, `cert_file`, `key_file`, `pid_file`, `log_file`, `file_path`, `audit_log_path`, `config_file` |
| **identifier / token-mask** | Leading delimiter-separated tokens replaced with `x`; suffix kept | `cluster_name`, `node_id`, `node_name`, `region`, `availability_zone` |

> **Special case — `path` inside a `secret` stanza:** The sanitizer is block-aware. When a `path` key appears directly inside a `secret "…" { }` stanza, its value is **fully redacted** (`***REDACTED***`) rather than tail-preserved, because the Vault secret path is itself sensitive. `path` in all other stanza types (e.g. `storage`, `seal`) retains the normal tail-preserve behaviour.

#### Generic fallback (unrecognised keys)

Custom stanza keys and env-style variable names that do not match any category above are classified by their **value content**, applied in priority order:

1. Key name contains `token`, `secret`, `password`, `passwd`, or `credential`, or ends with `_key` → `***REDACTED***`
2. Value looks like a URL or IP address → endpoint/anonymize policy
3. Value is an absolute path → path/tail-preserve policy
4. Value is a 3-or-more-token hyphen/underscore identifier → identifier/token-mask policy
5. Otherwise → passed through unchanged

### endpoint / anonymize — Examples

Keys: `vault_addr`, `api_addr`, `cluster_addr`, `cluster_address`, `address`, `redirect_addr`

| Input | Output |
|-------|--------|
| `169.182.4.100` | `x.x.x.100` *(last octet preserved)* |
| `hashicorp.com` | `hashicorp.com` *(2-label — unchanged)* |
| `vault.hashicorp.com` | `x.hashicorp.com` |
| `prd.ec2.hashicorp.com` | `x.x.hashicorp.com` |
| `https://vault.hashicorp.com:8200/v1` | `https://x.hashicorp.com:8200/v1` |
| `prd.ec2.hashicorp.com:8201` | `x.x.hashicorp.com:8201` |
| `localhost` / `127.0.0.1` / `0.0.0.0` / `[::]` | *(unchanged)* |
| `[2001:db8::1]` | `[x:x::1]` *(last hextet preserved; prior hextets replaced with `x`; loopback `[::1]` and wildcard `[::]` unchanged)* |
| `[fd00:abcd::10]` | `[x:x::10]` |

### path / tail-preserve — Examples

Keys: `path`, `tls_cert_file`, `tls_key_file`, `tls_client_ca_file`, `tls_ca_file`, `ca_cert`, `ca_path`, `cert_file`, `key_file`, `pid_file`, `log_file`, `file_path`, `audit_log_path`, `config_file`

Each leading directory segment is replaced with `...`; the last two segments are kept.
Paths with two or fewer segments are passed through unchanged.

| Input | Output |
|-------|--------|
| `/etc/ssl/vault/server.key` | `.../.../vault/server.key` |
| `/opt/vault/tls/tls.crt` | `.../.../tls/tls.crt` |
| `/opt/vault/data` | `.../vault/data` |
| `/vault/data` | `/vault/data` *(≤ 2 segments — unchanged)* |
| `C:\vault\tls\server.key` | `...\tls\server.key` *(Windows paths also supported)* |

### identifier / token-mask — Examples

Keys: `cluster_name`, `node_id`, `node_name`, `region`, `availability_zone`

Uses the first delimiter found (`-` takes priority over `_`).
Rule: keep the last half (rounded up) of tokens, replace the first half (rounded down) with `x`.
Single-token values (no delimiter) are passed through unchanged.

| Input | Output |
|-------|--------|
| `vault-prod-eu-west-1` | `x-x-eu-west-1` *(N=5, mask 2, keep 3)* |
| `us-east-1` | `x-east-1` *(N=3, mask 1, keep 2)* |
| `prod-cluster-01` | `x-cluster-01` *(N=3, mask 1, keep 2)* |
| `my_app_prod_us_east` | `x_x_prod_us_east` *(N=5, underscore delimiter, mask 2)* |
| `production` | `production` *(single token — unchanged)* |

### Before / After Example

Config before:

```hcl
vault_addr     = "https://vault.hashicorp.com:8200"
api_addr       = "https://prd.ec2.hashicorp.com:8200"
cluster_name   = "vault-prod-eu-west-1"
token          = "s.abc123"
tls_cert_file  = "/etc/ssl/vault/tls.crt"
tls_key_file   = "/etc/ssl/vault/server.key"

seal "awskms" {
  region     = "us-east-1"
  kms_key_id = "arn:aws:kms:us-east-1:123:key/abcd"
  access_key = "AKIAIOSFODNN7EXAMPLE"
  secret_key = "wJalrXUtnFEMI/K7MDENG"
}
```

Config after `vaultx sanitize`:

```hcl
vault_addr     = "https://x.hashicorp.com:8200"
api_addr       = "https://x.x.hashicorp.com:8200"
cluster_name   = "x-x-eu-west-1"
token          = "***REDACTED***"
tls_cert_file  = ".../.../vault/tls.crt"
tls_key_file   = ".../.../vault/server.key"

seal "awskms" {
  region     = "x-east-1"
  kms_key_id = "***REDACTED***"
  access_key = "***REDACTED***"
  secret_key = "***REDACTED***"
}
```

> **Note:** Telemetry-specific bespoke masking rules are deferred to a future release.
> Custom telemetry keys are handled by the generic fallback today.
>
> Log sanitization is also planned for a future release.

## Command-Line Options

| Flag | Description |
|------|-------------|
| `-format=json` | Output in pretty-printed JSON format |
| `-export=FILE` | Export data to specified file |
| `-help` | Show help message |

### Sanitize Subcommand Options

| Flag | Description |
|------|-------------|
| `-config=FILE` | Path to the config file to sanitize (flag form) |
| `<FILE>` | Path to the config file to sanitize (positional) |
| `-out=FILE` | Write sanitized output to FILE (default: stdout) |
| `-help` | Show sanitize help message |



https://github.com/user-attachments/assets/b7d5a6ec-b395-4be8-879e-c245506cec8b

## Authentication

VaultX supports two authentication methods:

1. **Environment Variable** (recommended):
```bash
export VAULT_TOKEN="your-vault-token"
vaultx
```

2. **Interactive Prompt**:
```bash
vaultx
# You'll be prompted: "Enter your Vault token:"
```

## Environment Variables

- `VAULT_TOKEN` - Vault authentication token
- `VAULT_ADDR` - Vault server address (e.g., https://vault.example.com:8200)
- `VAULT_SKIP_VERIFY` - Skip TLS certificate verification (not recommended for production)

## Output Examples

### CLI Output (Colorized)

```
Discovering Vault cluster nodes...
Discovered nodes:
https://vault-node-1:8200
https://vault-node-2:8200
https://vault-node-3:8200

=== Vault Status for https://vault-node-1:8200 ===
Key                                      Value
---                                      -----
Seal Type                                shamir
Initialized                              true
Sealed                                   false
...

=== Raft List Peers ===
Node       Address              State       Voter
----       -------              -----       -----
node-1     10.0.1.10:8201      leader      true
node-2     10.0.1.11:8201      follower    true
node-3     10.0.1.12:8201      follower    true
```

### JSON Output (Pretty-Printed)

```json
{
  "node_status": {
    "https://vault-node-1:8200": {
      "type": "shamir",
      "initialized": true,
      "sealed": false,
      "ha_enabled": true,
      "is_self": true,
      "active_time": "2024-01-15T10:30:00Z"
    }
  },
  "raft_peers": {
    "cli_parsed": [
      {
        "node": "node-1",
        "address": "10.0.1.10:8201",
        "state": "leader",
        "voter": "true"
      }
    ]
  },
  "operator_members": {...},
  "license": {...},
  "autopilot_state": {...},
  "autopilot_config": {...},
  "replication": {
    "dr_status": {...},
    "performance_status": {...}
  },
  "audit_devices": {...}
}
```

## Troubleshooting

### "Missing required dependencies"
Install the required tools:
```bash
# Install Vault CLI
# See: https://developer.hashicorp.com/vault/downloads

# Install jq
# macOS
brew install jq

# Ubuntu/Debian
apt-get install jq

# RHEL/CentOS
yum install jq
```

### "Invalid Vault token or connection failed"
- Verify your VAULT_TOKEN is valid
- Check that VAULT_ADDR points to the correct Vault server
- Ensure network connectivity to the Vault cluster

### Permission Errors
Ensure your Vault token has sufficient permissions to read:
- `sys/health`
- `sys/license/status`
- `sys/replication/dr/status`
- `sys/replication/performance/status`
- `sys/audit`

---

## VaultX AI Agent

The **VaultX AI Agent** adds a Python-based conversational layer on top of the existing bash diagnostic tool. It uses [Ollama](https://ollama.com) with open-source LLMs (default: `llama3.1:8b`) — everything runs locally with no external API calls and no cost.

### Architecture

```
User ↔ vaultx-agent (Python CLI) ↔ LLM (Ollama/local)
                                  ↔ vaultx (bash tool) ↔ Vault API
                                  ↔ vault-mcp-server   ↔ Vault API  [optional]
```

### Prerequisites

- **Python 3.11+**
- **Ollama** installed and running (`ollama serve`)
- The default model pulled: `ollama pull llama3.1:8b`
- The same `VAULT_ADDR` / `VAULT_TOKEN` environment variables used by the bash tool
- Optional for live MCP-backed Vault operations: **vault-mcp-server** (for example `uvx --from hashicorp/vault-mcp-server vault-mcp-server`)

### Installation

1. Create a virtual environment and install the Python dependencies:

```bash
python3 -m venv venv && source venv/bin/activate && pip3 install -r agent/requirements.txt
```

2. Make the entry-point script executable (if not already):

```bash
chmod +x vaultx-agent
```

### Usage

#### Interactive mode (default)

Start a conversational Q&A session about your Vault cluster:

```bash
./vaultx-agent
```

Example questions:
- "Is my cluster healthy?"
- "Are any nodes sealed?"
- "When does my license expire?"
- "Summarize the raft peers"
- "Are there any replication issues?"

Type `refresh` to re-collect diagnostic data, or `quit` / `Ctrl-C` to exit.

<img width="1803" height="555" alt="vault-agent" src="https://github.com/user-attachments/assets/9e39f0fb-a482-443a-8acf-adca63fb44d6" />


#### Report / support-ticket generation

Automatically collect all diagnostics, analyze them with the LLM, and produce a comprehensive Markdown report:

```bash
./vaultx-agent --generate-report
```

Save the report to a file:

```bash
./vaultx-agent --generate-report -o report.md
# or
./vaultx-agent -r -o report.md
```

#### Configuration flags

| Flag | Default | Description |
|------|---------|-------------|
| `--generate-report`, `-r` | — | Generate a support ticket report instead of interactive mode |
| `--model MODEL` | `llama3.1:8b` | Ollama model to use |
| `--ollama-host HOST` | `http://localhost:11434` | Ollama server URL |
| `--output FILE`, `-o FILE` | stdout | Save report to FILE (used with `--generate-report`) |
| `--mcp` | disabled | Enable MCP support and connect to `vault-mcp-server` |
| `--mcp-server-command CMD` | `vault-mcp-server` | Launch an MCP server over stdio |
| `--mcp-server-url URL` | — | Connect to an existing Streamable HTTP or SSE MCP endpoint |
| `--mcp-timeout SECS` | `30` | Timeout for MCP tool discovery and calls |
| `--help` | — | Show help message |

You can also run the agent as a Python module:

```bash
python -m agent.cli --help
```

#### MCP Integration

`vaultx-agent` keeps the existing local `vaultx` snapshot flow and adds optional live Vault tools via MCP.

- Local `vaultx_*` tools continue to answer snapshot-based diagnostics questions quickly.
- MCP tools are only enabled when `--mcp` is set or `VAULTX_MCP=true` is exported.
- When both are available, the agent prefers the local snapshot first and only calls MCP tools for live Vault operations or questions that are not covered by the cached diagnostics data.

Start a local MCP server over stdio:

```bash
./vaultx-agent --mcp --mcp-server-command "uvx --from hashicorp/vault-mcp-server vault-mcp-server"
```

Connect to a running MCP endpoint instead:

```bash
./vaultx-agent --mcp --mcp-server-url http://127.0.0.1:8000/mcp
```

Environment variable fallbacks are also supported:

```bash
export VAULTX_MCP=true
export VAULTX_MCP_SERVER_COMMAND="uvx --from hashicorp/vault-mcp-server vault-mcp-server"
./vaultx-agent
```

### Report Structure

The generated Markdown report includes:

- **Cluster Overview** — node count, versions, topology
- **Health Assessment** — overall status, per-node sealed/active/standby
- **Raft Consensus** — leader, voter list, unhealthy nodes
- **License Status** — expiration date and warnings
- **Replication** — DR and Performance replication status
- **Audit Devices** — configured backends
- **Findings & Recommendations** — prioritized list (CRITICAL / WARNING / INFO)
- **Raw Diagnostic Data** — full JSON appendix

### Agent Directory Structure

```
agent/
├── __init__.py      # Package metadata
├── cli.py           # CLI entry point
├── config.py        # Shared runtime configuration
├── llm.py           # Ollama LLM client wrapper
├── mcp_client.py    # MCP connection lifecycle and tool calls
├── tools.py         # Tool definitions wrapping vaultx -format=json
├── tool_registry.py # Unified local + MCP tool registry
├── prompts.py       # System prompts and templates
├── report.py        # Report generation logic
└── requirements.txt # Python dependencies
```

---

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is open source and available under the MIT License.

## Support

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/zaid-hc/vaultx).

## Changelog

### v1.2.0 (Latest)
- ✅ Added `sanitize` subcommand for redacting sensitive Vault configuration values
- ✅ Improved README documentation with sanitize usage and examples
- ✅ Updated project description to reflect diagnostic and reporting workflows

### v1.1.0
- ✅ Added automatic JSON pretty-printing with `jq`
- ✅ Updated CLI flags to use single dash convention
- ✅ Improved error handling

### v1.0.0
- Initial release
- Multi-node cluster support
- Colorized CLI output
- JSON export functionality
- Parallel data collection

---

**Note**: VaultX is designed for diagnostic purposes. Review collected or sanitized output before sharing it, even when using the sanitize option.
