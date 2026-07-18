#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TOOL_ROOT="$REPO_ROOT/tools/contract-modeling"
OUT="$TOOL_ROOT/out"
PYTHON=${PYTHON:-python3}
CANDIDATE_SHA=${CANDIDATE_SHA:-$(git -C "$REPO_ROOT" rev-parse HEAD)}

case "$CANDIDATE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*)
    test "${#CANDIDATE_SHA}" -eq 40
    ;;
  *)
    echo "invalid CANDIDATE_SHA: $CANDIDATE_SHA" >&2
    exit 1
    ;;
esac

test "$(git -C "$REPO_ROOT" rev-parse HEAD)" = "$CANDIDATE_SHA"

rm -rf "$OUT"
mkdir -p "$OUT"

"$PYTHON" "$TOOL_ROOT/fixtures/generate.py" > "$OUT/generate.log"

"$PYTHON" "$TOOL_ROOT/bin/evaluate_exact.py" \
  --candidate-sha "$CANDIDATE_SHA" \
  --repo-root "$REPO_ROOT" \
  --require-duckdb \
  --out "$OUT/semantic-packet.json" \
  > "$OUT/evaluate.log"

"$PYTHON" "$TOOL_ROOT/bin/evaluate_exact.py" \
  --candidate-sha "$CANDIDATE_SHA" \
  --repo-root "$REPO_ROOT" \
  --require-duckdb \
  --out "$OUT/semantic-packet-second.json" \
  > "$OUT/evaluate-second.log"

cmp "$OUT/semantic-packet.json" "$OUT/semantic-packet-second.json"

"$PYTHON" "$TOOL_ROOT/bin/run_selftest.py" \
  --candidate-sha "$CANDIDATE_SHA" \
  --repo-root "$REPO_ROOT" \
  --require-duckdb \
  --out "$OUT/selftest-receipt.json" \
  > "$OUT/selftest.log"

nix build --impure --no-link --print-out-paths --expr "
let
  flake = builtins.getFlake (toString $REPO_ROOT);
  pkgs = import flake.inputs.nixpkgs { system = \"x86_64-linux\"; };
in import $TOOL_ROOT/nix/materialize.nix {
  inherit pkgs;
  semanticPacket = $OUT/semantic-packet.json;
}
" > "$OUT/nix-store-path.txt"

test -s "$OUT/semantic-packet.json"
test -s "$OUT/selftest-receipt.json"
test -s "$OUT/nix-store-path.txt"

sha256sum \
  "$OUT/semantic-packet.json" \
  "$OUT/selftest-receipt.json" \
  "$OUT/nix-store-path.txt" \
  > "$OUT/proof-digests.txt"

cat "$OUT/selftest-receipt.json"
