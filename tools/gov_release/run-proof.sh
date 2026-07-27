#!/usr/bin/env bash
set -euo pipefail

python3 tools/gov_release/identity.py selftest
python3 -m unittest discover -s tools/gov_release/tests -p 'test_*.py'
python3 tools/check-gov-release-integration.py selftest --json
python3 tools/check-gov-release-integration.py canary --json

# Approval verifier proof is absorbed into the accepted primary CI surface.
first="$(mktemp)"
second="$(mktemp)"
manifest_a="$(mktemp)"
manifest_b="$(mktemp)"
result="$(mktemp -d)"
trap 'rm -f "$first" "$second" "$manifest_a" "$manifest_b"; rm -rf "$result"' EXIT

python3 tools/approval-receipt-verifier.py selftest > "$first"
python3 tools/approval-receipt-verifier.py selftest > "$second"
cmp "$first" "$second"
python3 tools/approval-receipt-verifier.py manifest > "$manifest_a"
python3 tools/approval-receipt-verifier.py manifest > "$manifest_b"
cmp "$manifest_a" "$manifest_b"

python3 - "$first" "$manifest_a" <<'PY'
import hashlib,json,sys
from pathlib import Path
selftest=json.load(open(sys.argv[1]))
manifest=json.load(open(sys.argv[2]))
assert selftest['status']=='PASS'
assert selftest['destructiveCases']==23
assert selftest['expectedAdapterManifestDigest']=='sha256:538ba7977bc9894bfcc2e2ae7f7e670b915f0302f318663546071d196f048724'
assert selftest['engineManifestDigest']==manifest['manifest_digest']
assert manifest['source_files'][0]['sha256']=='sha256:'+hashlib.sha256(Path('tools/approval-receipt-verifier.py').read_bytes()).hexdigest()
identity=json.load(open('contracts/approval_actor/v1/identity.json'))
assert identity['canonicalEvidenceShape']=='githubApprovalEvidence.v1'
assert identity['contractDigest']=='sha256:21abaeb0cfb4f76babe7f1f530d14e807ef1c236e891257199490a8c0bb9d03e'
def canonical_digest(path):
    value=json.load(open(path))
    return 'sha256:'+hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
for name,path in {
 'authorityGrant.v1':'contracts/approval_actor/v1/schemas/authority-grant.schema.json',
 'githubApprovalEvidence.v1':'contracts/approval_actor/v1/schemas/github-approval-evidence.schema.json',
 'approvalReceipt.v1':'contracts/approval_actor/v1/schemas/approval-receipt.schema.json',
 'implementationManifest.v1':'contracts/approval_actor/v1/schemas/implementation-manifest.schema.json',
}.items():
    assert canonical_digest(path)==identity['schemaDigests'][name]
fixture=json.load(open('contracts/approval_actor/v1/fixtures/github-approval-evidence.valid.json'))
schema=json.load(open('contracts/approval_actor/v1/schemas/github-approval-evidence.schema.json'))
assert set(fixture)==set(schema['required'])
assert fixture['kind']=='githubApprovalEvidence.v1' and fixture['status']=='COMPLETE'
assert fixture['adapter_manifest_digest']=='sha256:538ba7977bc9894bfcc2e2ae7f7e670b915f0302f318663546071d196f048724'
assert 'providerApprovalEvidence.v1' not in json.dumps(fixture)
PY

! grep -Ei '(^|[[:space:]])(import|from)[[:space:]]+(github|requests|httpx|urllib)' tools/approval-receipt-verifier.py
! grep -q 'providerApprovalEvidence.v1' tools/approval-receipt-verifier.py

nix-build --impure --expr '
  let
    pkgs = (builtins.getFlake "github:NixOS/nixpkgs/a799d3e3886da994fa307f817a6bc705ae538eeb").legacyPackages.x86_64-linux;
  in import ./nix/approval-receipt-verifier.nix { inherit pkgs; }
' -o "$result/package" >/dev/null
"$result/package/bin/approval-receipt-verifier" selftest > "$result/nix-selftest.json"
"$result/package/bin/approval-receipt-verifier" manifest > "$result/nix-manifest.json"
cmp "$first" "$result/nix-selftest.json"
cmp "$manifest_a" "$result/nix-manifest.json"
cat "$first"
python3 - "$first" <<'PY'
import json,sys
approval=json.load(open(sys.argv[1]))
print(json.dumps({
  'kind':'governance.govReleaseProofSummary.v2',
  'status':'candidate-pass',
  'approvalVerifier':{
    'status':approval['status'],
    'destructiveCases':approval['destructiveCases'],
    'engineManifestDigest':approval['engineManifestDigest'],
    'expectedAdapterManifestDigest':approval['expectedAdapterManifestDigest'],
    'canonicalEvidenceShape':'githubApprovalEvidence.v1',
  },
},sort_keys=True,separators=(',',':')))
PY
