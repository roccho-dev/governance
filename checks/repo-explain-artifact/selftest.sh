#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TOOL="$ROOT/tools/repo-explain-artifact.sh"
FIX="$ROOT/fixtures/repo-explain-artifact"
TMP="$(mktemp -d)"

bash -n "$TOOL"
bash "$TOOL" build --input "$FIX/accepted.jsonl" --repo roccho-dev/governance --required-root purpose:company:high-value-sale --audience public --out "$TMP/one"
test -s "$TMP/one/README.md"
test -s "$TMP/one/manifest.json"
test -s "$TMP/one/sources.jsonl"

echo "[OK] repo-explain-artifact selftest"
