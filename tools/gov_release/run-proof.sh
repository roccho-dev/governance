#!/usr/bin/env bash
set -euo pipefail

python3 tools/gov_release/identity.py selftest
python3 -m unittest discover -s tools/gov_release/tests -p 'test_*.py'
python3 tools/check-gov-release-integration.py selftest --json
python3 tools/check-gov-release-integration.py canary --json

# The approval verifier remains a separate package, but its recurring proof is
# absorbed into the existing accepted primary CI surface.
first="$(mktemp)"
second="$(mktemp)"
result="$(mktemp -d)"
trap 'rm -f "$first" "$second"; rm -rf "$result"' EXIT
python3 tools/approval-receipt-verifier.py selftest > "$first"
python3 tools/approval-receipt-verifier.py selftest > "$second"
cmp "$first" "$second"
grep -q '"status": "PASS"' "$first"
! grep -Ei '(^|[[:space:]])(import|from)[[:space:]]+(github|requests|httpx|urllib)' tools/approval-receipt-verifier.py
nix-build --impure --expr '
  let
    pkgs = (builtins.getFlake "github:NixOS/nixpkgs/a799d3e3886da994fa307f817a6bc705ae538eeb").legacyPackages.x86_64-linux;
  in import ./nix/approval-receipt-verifier.nix { inherit pkgs; }
' -o "$result/package" >/dev/null
"$result/package/bin/approval-receipt-verifier" selftest > "$result/nix-selftest.json"
cmp "$first" "$result/nix-selftest.json"
cat "$first"
