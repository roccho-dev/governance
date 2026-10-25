#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
python3 -m unittest discover -s "$root/tests" -v
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
"$root/run-proof.sh" "$tmp/out"
cmp "$tmp/out/receipt.json" "$tmp/out/receipt.json"
