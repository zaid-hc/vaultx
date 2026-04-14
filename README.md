# VaultX

A powerful diagnostic tool for HashiCorp Vault clusters that collects comprehensive health and configuration information.

## Overview

VaultX is a bash-based CLI tool designed to streamline Vault cluster diagnostics and troubleshooting. It gathers critical information about your Vault deployment including node status, Raft configuration, license details, replication status, and more - perfect for generating support tickets or debugging cluster issues.

## Features

- 🔍 **Comprehensive Diagnostics**: Collects all essential Vault cluster information in one command
- 🎨 **Colorized Output**: Beautiful, easy-to-read CLI output with color-coded status indicators
- 📊 **Pretty-Printed JSON**: Export diagnostic data in beautifully formatted JSON
- ⚡ **Parallel Data Collection**: Fast data gathering using parallel execution
- 🔐 **Secure Authentication**: Supports VAULT_TOKEN environment variable or interactive token input
- 🛡️ **Config Sanitization**: Strip sensitive values from config files before sharing with support

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

Use `vaultx sanitize` to redact sensitive values from a Vault config file before
sharing it with support teams.  No Vault connection or token is required.

### Basic Usage

```bash
# Print sanitized config to stdout
vaultx sanitize -config=config.hcl

# Positional form (equivalent)
vaultx sanitize config.hcl

# Write sanitized output to a file
vaultx sanitize -config=config.hcl -out=sanitized.hcl
```

### What Gets Redacted vs Masked

**Fully redacted** (replaced with `***REDACTED***`) — keys matched case-insensitively:

| Key |
|-----|
| `token` |
| `auth_token` |
| `api_key` |
| `secret` |
| `client_secret` |
| `kms_key` |
| `kms_key_id` |
| `private_key` |
| `password` |
| `access_key` |
| `secret_key` |

**Masked** — address/URL keys are never fully redacted; DNS hostnames are
anonymized by replacing each subdomain label with `x` while the registrable
domain (last two labels) is preserved.  Structure (scheme, port, path) is kept.

Keys that receive hostname masking (case-insensitive):
`vault_addr`, `api_addr`, `cluster_addr`, `cluster_address`, `address`, `redirect_addr`

| Input | Output |
|-------|--------|
| `169.182.4.100` | `x.x.x.100` |
| `hashicorp.com` | `hashicorp.com` *(2-label — unchanged)* |
| `vault.hashicorp.com` | `x.hashicorp.com` |
| `prd.ec2.hashicorp.com` | `x.x.hashicorp.com` |
| `https://vault.hashicorp.com:8200/v1` | `https://x.hashicorp.com:8200/v1` |
| `prd.ec2.hashicorp.com:8201` | `x.x.hashicorp.com:8201` |
| `localhost` / `127.0.0.1` / `0.0.0.0` / `[::]` | *(unchanged)* |
| `[2001:db8::1]` | `[x:x::1]` *(last hextet preserved; prior hextets replaced with `x`; loopback `[::1]` and wildcard `[::]` unchanged)* |
| `[fd00:abcd::10]` | `[x:x::10]` |

### Before / After Example

Config before:

```hcl
vault_addr   = "https://vault.hashicorp.com:8200"
api_addr     = "https://prd.ec2.hashicorp.com:8200"
token        = "s.abc123"
kms_key_id   = "arn:aws:kms:us-east-1:123:key/abcd"
cluster_name = "production"

seal "awskms" {
  region     = "us-east-1"
  kms_key_id = "arn:aws:kms:us-east-1:123:key/abcd"
  access_key = "AKIAIOSFODNN7EXAMPLE"
  secret_key = "wJalrXUtnFEMI/K7MDENG"
}
```

Config after `vaultx sanitize`:

```hcl
vault_addr   = "https://x.hashicorp.com:8200"
api_addr     = "https://x.x.hashicorp.com:8200"
token        = "***REDACTED***"
kms_key_id   = "***REDACTED***"
cluster_name = "production"

seal "awskms" {
  region     = "us-east-1"
  kms_key_id = "***REDACTED***"
  access_key = "***REDACTED***"
  secret_key = "***REDACTED***"
}
```

> **Note:** Log sanitization is planned for a future release.

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
```

### Prerequisites

- **Python 3.11+**
- **Ollama** installed and running (`ollama serve`)
- The default model pulled: `ollama pull llama3.1:8b`
- The same `VAULT_ADDR` / `VAULT_TOKEN` environment variables used by the bash tool

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
| `--help` | — | Show help message |

You can also run the agent as a Python module:

```bash
python -m agent.cli --help
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
├── llm.py           # Ollama LLM client wrapper
├── tools.py         # Tool definitions wrapping vaultx -format=json
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

### v1.1.0 (Latest)
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

**Note**: This tool is designed for diagnostic purposes only. Always review the data collected before sharing, as it may contain sensitive cluster information.
