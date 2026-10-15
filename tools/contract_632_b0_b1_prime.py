#!/usr/bin/env python3
import argparse,json
from pathlib import Path

p=argparse.ArgumentParser()
for n in ('b0','b1','member','out'): p.add_argument('--'+n,required=True)
a=p.parse_args(); b0=Path(a.b0)/'ops-bundle'; b1=Path(a.b1)
expected={'sources/observer/source','source-bindings.json','bound-verification.json','contract-diff-input.json','contract-diff-admission.json','contract-diff-positive.json','negative-contract-drift-input.json','negative-contract-drift-admission.json','contract-diff-negative-contract-drift.json','negative-missing-observation-input.json','negative-missing-observation-admission.json','contract-diff-negative-missing-observation.json','negative-wrong-candidate-input.json','negative-wrong-candidate-admission.json','contract-diff-negative-wrong-candidate.json','negative-missing-admission-input.json','phase4-evidence.json','bundle-manifest.json'}
paths0={x.relative_to(b0).as_posix() for x in b0.rglob('*') if x.is_file()}; paths1={x.relative_to(b1).as_posix() for x in b1.rglob('*') if x.is_file()}
if paths0!=paths1: raise SystemExit('bundle-path-set')
changed={x for x in paths0 if (b0/x).read_bytes()!=(b1/x).read_bytes()}
if changed!=expected: raise SystemExit('unexpected-delta-files:'+json.dumps(sorted(changed)))
for x in ('run-scope.json','negative-missing-admission-admission.json','contract-diff-negative-missing-admission.json','ops-final-ci-consumer-receipt.json'):
    if (b0/x).read_bytes()!=(b1/x).read_bytes(): raise SystemExit('stable-byte-drift:'+x)
v2=json.loads((Path(a.b0)/'package-contract-member.json').read_text()); v3=json.loads(Path(a.member).read_text())
keys=('status','authority','adoption','releasePublished','claimCeiling','scopeId','obligationId','acceptedRequirementDigest','contractDiffStatus','negativeStatus','remaining','evidenceBound','observerMeaningVerified','evidenceReconstructed','sourceBytesVerified','receiptReplayed','comparatorReplayed')
for key in keys:
    if v2[key]!=v3[key]: raise SystemExit('semantic-member-drift:'+key)
if v2['opsCandidate']!=v3['targetCandidate'] or v2['opsCandidateSourcesVerified']!=v3['targetSourcesVerified'] or v2['acceptedGovernanceRevision']!=v3['acceptedRequirementRevision']: raise SystemExit('semantic-member-mapping')
report={'kind':'governance.contract632.b0B1PrimePortEquivalence.v1','status':'pass','authority':False,'semanticInvariant':True,'stableByteInvariant':True,'expectedDeltaClosed':True,'runtimeSeparated':True,'lowerProofPreservedForOps':True,'changedFiles':sorted(changed)}
Path(a.out).write_text(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
