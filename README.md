# VaultX

A powerful diagnostic tool for HashiCorp Vault clusters that collects comprehensive health and configuration information.

## Overview

VaultX is a bash-based CLI tool designed to streamline Vault cluster diagnostics and troubleshooting. It gathers critical information about your Vault deployment including node status, Raft configuration, license details, replication status, and more - perfect for generating support tickets or debugging cluster issues.

## Features

- 🔍 **Comprehensive Diagnostics**: Collects all essential Vault cluster information in one command
- 🎨 **Colorized Output**: Beautiful, easy-to-read CLI output with color-coded status indicators
- 📊 **JSON Export**: Export diagnostic data in JSON format for programmatic processing
- ⚡ **Parallel Data Collection**: Fast data gathering using parallel execution
- 🔐 **Secure Authentication**: Supports VAULT_TOKEN environment variable or interactive token input
- ⏱️ **Configurable Timeouts**: Adjust timeouts for slow or distributed clusters
- 📝 **Detailed Logging**: Built-in logging system for debugging and audit trails

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
- `jq` - JSON processor for parsing responses
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

Output diagnostics in JSON format:
```bash
vaultx -format=json
```

### Export to File

Export diagnostic data to a file:
```bash
vaultx --export=diagnostics.json
```

### Custom Timeout

Increase timeout for slow clusters:
```bash
vaultx --timeout=10
```

### Custom Config File

Use a custom configuration file:
```bash
vaultx --config=/path/to/config.conf
```

### Help

Display help message:
```bash
vaultx --help
```

## Configuration

VaultX can be configured using a configuration file at `~/.vaultx.conf`. Available options:

```bash
# Default timeout for Vault operations (seconds)
TIMEOUT=5

# Log level: DEBUG, INFO, WARN, ERROR
LOG_LEVEL="INFO"

# Log file location
LOG_FILE="${HOME}/.vaultx.log"
```

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

### JSON Output

```json
{
  "node_status": {
    "https://vault-node-1:8200": {
      "type": "shamir",
      "initialized": true,
      "sealed": false,
      ...
    }
  },
  "raft_peers": {...},
  "operator_members": {...},
  "license": {...},
  "autopilot_state": {...},
  "autopilot_config": {...},
  "replication": {...},
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
- Try increasing the timeout: `vaultx --timeout=10`

### Permission Errors
Ensure your Vault token has sufficient permissions to read:
- `sys/health`
- `sys/license/status`
- `sys/replication/dr/status`
- `sys/replication/performance/status`
- `sys/audit`

## Logging

VaultX maintains logs at `~/.vaultx.log` by default. Log levels:
- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARN**: Warning messages
- **ERROR**: Error messages

View logs:
```bash
tail -f ~/.vaultx.log
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is open source and available under the MIT License.

## Support

For issues, questions, or contributions, please visit the [GitHub repository](https://github.com/zaid-hc/vaultx).

## Changelog

### v1.0.0
- Initial release
- Multi-node cluster support
- Colorized CLI output
- JSON export functionality
- Parallel data collection
- Configurable timeouts
- Comprehensive error handling

---

**Note**: This tool is designed for diagnostic purposes only. Always review the data collected before sharing, as it may contain sensitive cluster information.