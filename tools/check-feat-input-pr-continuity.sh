#!/usr/bin/env bash
set -euo pipefail

root="."
base_ref="${BASE_REF:-origin/main}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --root)
      root="$2"
      shift 2
      ;;
    --base-ref)
      base_ref="$2"
      shift 2
      ;;
    *)
      echo "usage: $0 [--root ROOT] [--base-ref REF]" >&2
      exit 2
      ;;
  esac
done

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

git -C "$root" show "${base_ref}:records/specs/package-contract.v1.jsonl" \
  > "$tmpdir/base-package-contract.v1.jsonl"

"${PYTHON:-python3}" "$root/tools/check-feat-input-continuity.py" \
  --root "$root" \
  --require-base \
  --base-package-contract "$tmpdir/base-package-contract.v1.jsonl"
