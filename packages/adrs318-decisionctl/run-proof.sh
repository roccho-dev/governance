#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
out="${1:-$root/out}"
python3 "$root/decisionctl.py" run \
  --events "$root/fixtures/events.valid.jsonl" \
  --grants "$root/fixtures/grants.valid.jsonl" \
  --out "$out"
python3 "$root/decisionctl.py" verify --out "$out"
