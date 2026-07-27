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
assert identity['status']=='ACCEPTED'
assert identity['adrsAcceptedMerge']=='70244fa200d8717c61b514432c54bed4248028d9'
assert identity['opsMergedCommit']=='a622192703c53fea4890a3ad3618e2a0ac85032f'
assert identity['admission']=='ALLOW_WITH_ACCEPTED_EXCEPTION'
assert identity['admissionExceptionDigest']=='sha256:748ab4ccc62bc60c6bdc8c38a9d64d121f6fe0340907a935873c98971ca17f91'
assert identity['fullCanonicalGreen'] is False
assert identity['canonicalEvidenceShape']=='githubApprovalEvidence.v1'
assert identity['contractDigest']=='sha256:53e9fa1053c8a2f003765c6af2e8a90114f6470b46c9cc28d45eb3562518af0b'
assert identity['opsAdapterManifestDigest']=='sha256:538ba7977bc9894bfcc2e2ae7f7e670b915f0302f318663546071d196f048724'
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
assert fixture['adapter_manifest_digest']==identity['opsAdapterManifestDigest']
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
    'mergedAdrsBound':True,
    'mergedOpsBound':True,
  },
},sort_keys=True,separators=(',',':')))
PY
