#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TOOL="$ROOT/tools/repo-explain-artifact.sh"
FIX="$ROOT/fixtures/repo-explain-artifact"
TMP="$(mktemp -d)"

bash -n "$TOOL"
"$TOOL" build --input "$FIX/accepted.jsonl" --repo roccho-dev/governance --required-root purpose:company:high-value-sale --audience public --out "$TMP/one"
test -s "$TMP/one/README.md"
test -s "$TMP/one/manifest.json"
test -s "$TMP/one/sources.jsonl"
"$TOOL" build --input "$FIX/accepted.jsonl" --repo roccho-dev/governance --required-root purpose:company:high-value-sale --audience public --out "$TMP/two"
cmp "$TMP/one/README.md" "$TMP/two/README.md"
cmp "$TMP/one/manifest.json" "$TMP/two/manifest.json"
cmp "$TMP/one/sources.jsonl" "$TMP/two/sources.jsonl"

if "$TOOL" build --input "$FIX/no-accepted-decision.jsonl" --repo roccho-dev/governance --required-root purpose:company:high-value-sale --audience public --out "$TMP/case1" 2>/dev/null; then
  echo "negative fixture unexpectedly passed: no-accepted-decision" >&2
  exit 1
fi
if "$TOOL" build --input "$FIX/wrong-root.jsonl" --repo roccho-dev/governance --required-root purpose:company:high-value-sale --audience public --out "$TMP/case2" 2>/dev/null; then
  echo "negative fixture unexpectedly passed: wrong-root" >&2
  exit 1
fi
if "$TOOL" build --input "$FIX/purpose-cycle.jsonl" --repo roccho-dev/governance --required-root purpose:company:high-value-sale --audience public --out "$TMP/case3" 2>/dev/null; then
  echo "negative fixture unexpectedly passed: purpose-cycle" >&2
  exit 1
fi

echo "[OK] repo-explain-artifact selftest"
