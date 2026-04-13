#!/usr/bin/env bash
# Tests for `vaultx sanitize` subcommand.
# Run from the repository root:  bash tests/test_sanitize.sh

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULTX="${SCRIPT_DIR}/../vaultx"
TMPDIR_BASE="$(mktemp -d)" || { echo "ERROR: failed to create temp dir" >&2; exit 1; }
PASS=0
FAIL=0

cleanup() { rm -rf "$TMPDIR_BASE"; }
trap cleanup EXIT

# ---------- helpers ----------

make_cfg() {
  # make_cfg <filename> <content>
  local f="${TMPDIR_BASE}/$1"
  printf '%s' "$2" > "$f"
  echo "$f"
}

run_sanitize() {
  # run_sanitize <file> [extra args...]
  bash "$VAULTX" sanitize "$@"
}

assert_contains() {
  local test_name="$1" expected="$2" actual="$3"
  if echo "$actual" | grep -qF "$expected"; then
    echo "  PASS: $test_name"
    ((PASS++))
  else
    echo "  FAIL: $test_name"
    echo "    expected to find : $expected"
    echo "    in output        : $actual"
    ((FAIL++))
  fi
}

assert_not_contains() {
  local test_name="$1" not_expected="$2" actual="$3"
  if echo "$actual" | grep -qF "$not_expected"; then
    echo "  FAIL: $test_name"
    echo "    expected NOT to find : $not_expected"
    echo "    but found in output  : $actual"
    ((FAIL++))
  else
    echo "  PASS: $test_name"
    ((PASS++))
  fi
}

assert_exit_nonzero() {
  local test_name="$1" exit_code="$2"
  if [[ "$exit_code" -ne 0 ]]; then
    echo "  PASS: $test_name (exit $exit_code)"
    ((PASS++))
  else
    echo "  FAIL: $test_name (expected non-zero exit, got 0)"
    ((FAIL++))
  fi
}

assert_exit_zero() {
  local test_name="$1" exit_code="$2"
  if [[ "$exit_code" -eq 0 ]]; then
    echo "  PASS: $test_name"
    ((PASS++))
  else
    echo "  FAIL: $test_name (expected exit 0, got $exit_code)"
    ((FAIL++))
  fi
}

# ---------- 1. Sensitive keys are redacted ----------
echo "=== 1. Sensitive key redaction ==="

cfg=$(make_cfg cfg1.hcl 'token = "s.abc123"
auth_token = "tok456"
api_key = "k-abcdef"
secret = "topsecret"
client_secret = "cs-xyz"
kms_key = "kmsval"
kms_key_id = "arn:aws:kms:us-east-1:123:key/abcd"
private_key = "-----BEGIN RSA PRIVATE KEY-----"
password = "hunter2"
access_key = "AKIAIOSFODNN7EXAMPLE"
secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
')
out=$(run_sanitize "$cfg")
ec=$?
assert_exit_zero "exit 0 on success" "$ec"
assert_contains     "token redacted"        'token = "***REDACTED***"'         "$out"
assert_contains     "auth_token redacted"   'auth_token = "***REDACTED***"'    "$out"
assert_contains     "api_key redacted"      'api_key = "***REDACTED***"'       "$out"
assert_contains     "secret redacted"       'secret = "***REDACTED***"'        "$out"
assert_contains     "client_secret redacted" 'client_secret = "***REDACTED***"' "$out"
assert_contains     "kms_key redacted"      'kms_key = "***REDACTED***"'       "$out"
assert_contains     "kms_key_id redacted"   'kms_key_id = "***REDACTED***"'    "$out"
assert_contains     "private_key redacted"  'private_key = "***REDACTED***"'   "$out"
assert_contains     "password redacted"     'password = "***REDACTED***"'      "$out"
assert_contains     "access_key redacted"   'access_key = "***REDACTED***"'    "$out"
assert_contains     "secret_key redacted"   'secret_key = "***REDACTED***"'    "$out"
assert_not_contains "no real token value"   "s.abc123"                          "$out"
assert_not_contains "no real password"      "hunter2"                           "$out"
assert_not_contains "no real access_key"    "AKIAIOSFODNN7EXAMPLE"              "$out"

# ---------- 2. Non-sensitive keys unchanged ----------
echo "=== 2. Non-sensitive keys unchanged ==="

cfg=$(make_cfg cfg2.hcl 'cluster_name = "production"
ui = true
disable_mlock = true
log_level = "info"
')
out=$(run_sanitize "$cfg")
assert_contains "cluster_name preserved" 'cluster_name = "production"' "$out"
assert_contains "ui preserved"           'ui = true'                   "$out"
assert_contains "disable_mlock preserved" 'disable_mlock = true'       "$out"
assert_contains "log_level preserved"    'log_level = "info"'          "$out"

# ---------- 3. Nested structures sanitized ----------
echo "=== 3. Nested structures sanitized ==="

cfg=$(make_cfg cfg3.hcl 'storage "raft" {
  path = "/opt/vault/data"
  secret_key = "raftkey123"
  access_key = "AKIAIOSFODNN7EXAMPLE"
}

seal "awskms" {
  region     = "us-east-1"
  kms_key_id = "arn:aws:kms:us-east-1:123:key/abcd"
  access_key = "AKIA..."
  secret_key = "secret..."
}

listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_cert_file = "/opt/vault/tls/tls.crt"
  token         = "not-a-real-token"
}
')
out=$(run_sanitize "$cfg")
assert_contains "nested secret_key redacted"  'secret_key = "***REDACTED***"'  "$out"
assert_contains "nested access_key redacted"  'access_key = "***REDACTED***"'  "$out"
assert_contains "nested kms_key_id redacted"  'kms_key_id = "***REDACTED***"'  "$out"
assert_contains "nested token redacted"       'token         = "***REDACTED***"' "$out"
assert_contains "non-sensitive path preserved" 'path = "/opt/vault/data"'       "$out"
assert_contains "non-sensitive address preserved" 'address       = "0.0.0.0:8200"' "$out"
assert_not_contains "no real kms key" "arn:aws:kms" "$out"

# ---------- 4. vault_addr plain IPv4 masking ----------
echo "=== 4. vault_addr IPv4 masking ==="

cfg=$(make_cfg cfg4.hcl 'vault_addr = "169.182.4.100"')
out=$(run_sanitize "$cfg")
assert_contains     "IPv4 last octet kept"  'vault_addr = "x.x.x.100"'    "$out"
assert_not_contains "IPv4 no real IP"       "169.182.4.100"                "$out"

cfg=$(make_cfg cfg4b.hcl 'vault_addr = "10.0.1.5"')
out=$(run_sanitize "$cfg")
assert_contains "IPv4 10.0.1.5 masked" 'vault_addr = "x.x.x.5"' "$out"

# ---------- 5. vault_addr plain DNS masking ----------
echo "=== 5. vault_addr DNS masking ==="

cfg=$(make_cfg cfg5.hcl 'vault_addr = "vault.hashicorp.com"')
out=$(run_sanitize "$cfg")
assert_contains     "DNS last two labels kept" 'vault_addr = "x.hashicorp.com"' "$out"
assert_not_contains "DNS no full host"         "vault.hashicorp.com"             "$out"

cfg=$(make_cfg cfg5b.hcl 'vault_addr = "vault.com"')
out=$(run_sanitize "$cfg")
assert_contains "two-label DNS unchanged" 'vault_addr = "vault.com"' "$out"

cfg=$(make_cfg cfg5c.hcl 'vault_addr = "myvault"')
out=$(run_sanitize "$cfg")
assert_contains "single-label DNS masked" 'vault_addr = "x"' "$out"

# ---------- 6. vault_addr URL masking (scheme/port/path preserved) ----------
echo "=== 6. vault_addr URL masking ==="

cfg=$(make_cfg cfg6.hcl 'vault_addr = "https://vault.hashicorp.com:8200/v1"')
out=$(run_sanitize "$cfg")
assert_contains "URL scheme preserved"   "https://"                              "$out"
assert_contains "URL port preserved"     ":8200"                                 "$out"
assert_contains "URL path preserved"     "/v1"                                   "$out"
assert_contains "URL host masked"        'vault_addr = "https://x.hashicorp.com:8200/v1"' "$out"
assert_not_contains "URL real host gone" "vault.hashicorp.com"                   "$out"

cfg=$(make_cfg cfg6b.hcl 'vault_addr = "http://10.0.0.200:8200/path?q=1"')
out=$(run_sanitize "$cfg")
assert_contains "URL IPv4 masked with path+query" 'vault_addr = "http://x.x.x.200:8200/path?q=1"' "$out"

cfg=$(make_cfg cfg6c.hcl 'vault_addr = "https://internal.vault.example.corp:8300"')
out=$(run_sanitize "$cfg")
assert_contains "long FQDN URL masked" 'vault_addr = "https://x.x.example.corp:8300"' "$out"

# ---------- 7. localhost / loopback preserved ----------
echo "=== 7. Loopback behavior ==="

cfg=$(make_cfg cfg7a.hcl 'vault_addr = "localhost"')
out=$(run_sanitize "$cfg")
assert_contains "localhost preserved" 'vault_addr = "localhost"' "$out"

cfg=$(make_cfg cfg7b.hcl 'vault_addr = "127.0.0.1"')
out=$(run_sanitize "$cfg")
assert_contains "127.0.0.1 preserved" 'vault_addr = "127.0.0.1"' "$out"

cfg=$(make_cfg cfg7c.hcl 'vault_addr = "http://localhost:8200"')
out=$(run_sanitize "$cfg")
assert_contains "http://localhost URL preserved" 'vault_addr = "http://localhost:8200"' "$out"

cfg=$(make_cfg cfg7d.hcl 'vault_addr = "http://127.0.0.1:8200/v1"')
out=$(run_sanitize "$cfg")
assert_contains "http://127.0.0.1 URL preserved" 'vault_addr = "http://127.0.0.1:8200/v1"' "$out"

# ---------- 8. IPv6 behavior ----------
echo "=== 8. IPv6 behavior (v1: full host redaction) ==="

cfg=$(make_cfg cfg8a.hcl 'vault_addr = "[2001:db8::1]"')
out=$(run_sanitize "$cfg")
assert_contains "bare IPv6 redacted"      '[REDACTED_IPv6]' "$out"
assert_not_contains "real IPv6 not present" "2001:db8"      "$out"

cfg=$(make_cfg cfg8b.hcl 'vault_addr = "http://[2001:db8::1]:8200"')
out=$(run_sanitize "$cfg")
assert_contains     "IPv6 URL host redacted"    '[REDACTED_IPv6]'  "$out"
assert_contains     "IPv6 URL scheme preserved" "http://"          "$out"
assert_contains     "IPv6 URL port preserved"   ":8200"            "$out"
assert_not_contains "real IPv6 address gone"    "2001:db8"         "$out"

cfg=$(make_cfg cfg8c.hcl 'vault_addr = "http://[::1]:8200"')
out=$(run_sanitize "$cfg")
assert_contains "IPv6 loopback preserved" 'vault_addr = "http://[::1]:8200"' "$out"

# ---------- 9. Malformed config / error handling ----------
echo "=== 9. Error handling ==="

out=$(run_sanitize /nonexistent/path/config.hcl 2>&1)
ec=$?
assert_exit_nonzero "missing file exits non-zero" "$ec"
assert_contains     "missing file error message"  "not found" "$out"

out=$(bash "$VAULTX" sanitize 2>&1)
ec=$?
assert_exit_nonzero "no args exits non-zero"    "$ec"
assert_contains     "no args error message"     "No config file specified" "$out"

out=$(bash "$VAULTX" sanitize --unknown-flag 2>&1)
ec=$?
assert_exit_nonzero "unknown flag exits non-zero" "$ec"

# Empty file should succeed with empty output
cfg=$(make_cfg empty.hcl '')
out=$(run_sanitize "$cfg")
ec=$?
assert_exit_zero "empty file exits 0" "$ec"

# File with only comments should pass through unchanged
cfg=$(make_cfg comments.hcl '# This is a comment
# Another comment
')
out=$(run_sanitize "$cfg")
assert_contains "comments passed through" "# This is a comment" "$out"

# ---------- 10. Mixed-case key matching ----------
echo "=== 10. Mixed-case key matching ==="

cfg=$(make_cfg cfg10.hcl 'Token = "s.abc"
TOKEN = "t.xyz"
KMS_KEY_ID = "arn:123"
VAULT_ADDR = "https://vault.mycompany.com:8200"
Password = "hunter2"
')
out=$(run_sanitize "$cfg")
assert_contains     "Token (title case) redacted"   'Token = "***REDACTED***"'         "$out"
assert_contains     "TOKEN (upper) redacted"         'TOKEN = "***REDACTED***"'         "$out"
assert_contains     "KMS_KEY_ID (upper) redacted"    'KMS_KEY_ID = "***REDACTED***"'    "$out"
assert_contains     "VAULT_ADDR (upper) masked"      'VAULT_ADDR = "https://x.mycompany.com:8200"' "$out"
assert_contains     "Password (title) redacted"      'Password = "***REDACTED***"'      "$out"
assert_not_contains "no real token"  "s.abc"          "$out"
assert_not_contains "no real password" "hunter2"      "$out"

# ---------- 11. -out flag writes to file ----------
echo "=== 11. -out flag ==="

cfg=$(make_cfg cfg11.hcl 'token = "s.outtest"
cluster_name = "prod"
')
out_file="${TMPDIR_BASE}/sanitized.hcl"
stderr_out=$(run_sanitize "$cfg" -out="$out_file" 2>&1)
ec=$?
assert_exit_zero "out flag exits 0" "$ec"
assert_contains  "out flag writes confirmation to stderr" "Sanitized config written to:" "$stderr_out"
file_content=$(cat "$out_file" 2>/dev/null)
assert_contains     "out file has redacted token"     'token = "***REDACTED***"' "$file_content"
assert_contains     "out file has unchanged key"      'cluster_name = "prod"'    "$file_content"
assert_not_contains "out file has no real token"      "s.outtest"                "$file_content"

# ---------- 12. -config=<file> flag form ----------
echo "=== 12. -config flag form ==="

cfg=$(make_cfg cfg12.hcl 'password = "p@ssw0rd"
vault_addr = "https://vault.corp.io:8200"
')
out=$(bash "$VAULTX" sanitize -config="$cfg")
assert_contains     "-config= flag redacts password"       'password = "***REDACTED***"'              "$out"
assert_contains     "-config= flag masks vault_addr"       'vault_addr = "https://x.corp.io:8200"'    "$out"
assert_not_contains "-config= no real password"            "p@ssw0rd"                                 "$out"

# ---------- 13. DNS anonymization — extended coverage ----------
echo "=== 13. DNS anonymization (multi-key and multi-level subdomains) ==="

# 13a. URL with multi-level subdomain (api_addr)
cfg=$(make_cfg cfg13a.hcl 'api_addr = "https://prd.ec2.hashicorp.com:8200"')
out=$(run_sanitize "$cfg")
assert_contains     "api_addr multi-level subdomain masked" \
                    'api_addr = "https://x.x.hashicorp.com:8200"' "$out"
assert_not_contains "api_addr real host gone" "prd.ec2.hashicorp.com" "$out"

# 13b. URL with single subdomain (cluster_addr)
cfg=$(make_cfg cfg13b.hcl 'cluster_addr = "https://vault.hashicorp.com:8201"')
out=$(run_sanitize "$cfg")
assert_contains     "cluster_addr single subdomain masked" \
                    'cluster_addr = "https://x.hashicorp.com:8201"' "$out"
assert_not_contains "cluster_addr real host gone" "vault.hashicorp.com" "$out"

# 13c. Bare registrable domain (no subdomain) — should be unchanged
cfg=$(make_cfg cfg13c.hcl 'api_addr = "https://hashicorp.com:8200"')
out=$(run_sanitize "$cfg")
assert_contains "bare registrable domain unchanged" \
                'api_addr = "https://hashicorp.com:8200"' "$out"

# 13d. host:port form (address key — listener)
cfg=$(make_cfg cfg13d.hcl 'address = "prd.ec2.hashicorp.com:8200"')
out=$(run_sanitize "$cfg")
assert_contains     "host:port multi-level subdomain masked" \
                    'address = "x.x.hashicorp.com:8200"' "$out"
assert_not_contains "host:port real host gone" "prd.ec2.hashicorp.com" "$out"

# 13e. IPv6 literal in address key — scheme/port preserved, IPv6 redacted (not domain-masked)
cfg=$(make_cfg cfg13e.hcl 'cluster_addr = "https://[2001:db8::1]:8201"')
out=$(run_sanitize "$cfg")
assert_contains     "IPv6 address redacted"     '[REDACTED_IPv6]'   "$out"
assert_contains     "IPv6 scheme preserved"     "https://"          "$out"
assert_contains     "IPv6 port preserved"       ":8201"             "$out"
assert_not_contains "IPv6 real address gone"    "2001:db8"          "$out"

# 13f. redirect_addr
cfg=$(make_cfg cfg13f.hcl 'redirect_addr = "https://node1.vault.example.com:8200"')
out=$(run_sanitize "$cfg")
assert_contains     "redirect_addr masked" \
                    'redirect_addr = "https://x.x.example.com:8200"' "$out"

# 13g. cluster_address (in listener stanza)
cfg=$(make_cfg cfg13g.hcl 'cluster_address = "active.vault.example.com:8201"')
out=$(run_sanitize "$cfg")
assert_contains     "cluster_address host:port masked" \
                    'cluster_address = "x.x.example.com:8201"' "$out"

# 13h. 0.0.0.0 bind address in address/cluster_address keys — preserved unchanged
cfg=$(make_cfg cfg13h.hcl 'address         = "0.0.0.0:8200"
cluster_address = "0.0.0.0:8201"
')
out=$(run_sanitize "$cfg")
assert_contains "0.0.0.0 address preserved"         'address         = "0.0.0.0:8200"'  "$out"
assert_contains "0.0.0.0 cluster_address preserved" 'cluster_address = "0.0.0.0:8201"'  "$out"

# 13i. vault_addr with multi-level subdomain (update existing behavior confirmation)
cfg=$(make_cfg cfg13i.hcl 'vault_addr = "https://prd.ec2.hashicorp.com:8200/v1"')
out=$(run_sanitize "$cfg")
assert_contains "vault_addr multi-level multi-label masked" \
                'vault_addr = "https://x.x.hashicorp.com:8200/v1"' "$out"

# ---------- Summary ----------
echo ""
echo "=================================="
echo "Results: ${PASS} passed, ${FAIL} failed"
echo "=================================="

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
