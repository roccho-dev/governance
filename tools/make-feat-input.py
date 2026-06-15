#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, hashlib, collections

def read_jsonl(path):
    for line in pathlib.Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            yield json.loads(line)

def canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def main():
    ap=argparse.ArgumentParser(description='Project accepted JSONL package contract into feat.input.v1 JSON.')
    ap.add_argument('root')
    ap.add_argument('package')
    ap.add_argument('--out', default='-')
    args=ap.parse_args()
    root=pathlib.Path(args.root)
    records={r['packageId']:r for r in read_jsonl(root/'governance-records-main/records/specs/package-contract.v1.jsonl')}
    if args.package not in records:
        raise SystemExit(f'unknown package: {args.package}')
    edges=[e for e in read_jsonl(root/'governance-records-main/records/specs/dependency-edge.v1.jsonl') if e['fromPackageId']==args.package]
    r=records[args.package]
    d=r['definition']
    payload={'packageId':args.package,'specId':r['specId'],'status':r['status'],'successorRepoId':d.get('successorRepoId'),'repoSourceUri':d.get('repoSourceUri'),'officialOutput':d.get('officialOutput'),'requiredOutputs':d.get('requiredOutputs') or [],'requiredChecks':d.get('requiredChecks') or [],'requiredCheckPackages':d.get('requiredCheckPackages') or [],'requiredCommands':d.get('requiredCommands') or [],'allowedPaths':d.get('allowedPaths') or [],'forbiddenPaths':d.get('forbiddenPaths') or [],'runtimeRequirements':d.get('runtimeRequirements'),'preflightRequiredTools':d.get('preflightRequiredTools') or [],'dependencyLock':edges,'recordDigest':r['recordDigest']}
    projection_digest=hashlib.sha256(canon(payload)).hexdigest()
    feat={'kind':'feat.input.v1','packageId':args.package,'specId':r['specId'],'status':'ready' if r['status']=='accepted' else ('planned-blocked' if r['status']=='planned' else 'deprecated-decision-needed'),'sourceAuthority':'governance-records-main/records/specs/package-contract.v1.jsonl','rawAdrDirectAuthority':False,'projectionDigest':projection_digest,'repoOperation':{'targetRepoId':d.get('successorRepoId'),'repoSourceUri':d.get('repoSourceUri'),'allowedPaths':d.get('allowedPaths') or [],'forbiddenPaths':d.get('forbiddenPaths') or []},'environmentBuildDefinition':{'kind':'governance.environmentBuildDefinition.v1','sourceOfTruth':'package-contract.v1.jsonl','package':args.package,'targetPackage':args.package,'repoId':d.get('successorRepoId'),'officialOutput':d.get('officialOutput'),'requiredOutputs':d.get('requiredOutputs') or [],'requiredChecks':d.get('requiredChecks') or [],'requiredCommands':d.get('requiredCommands') or [],'runtimeRequirements':d.get('runtimeRequirements'),'preflightRequiredTools':d.get('preflightRequiredTools') or []},'dependencyLock':edges}
    text=json.dumps(feat, ensure_ascii=False, indent=2, sort_keys=True)+'\n'
    if args.out == '-':
        print(text, end='')
    else:
        pathlib.Path(args.out).write_text(text, encoding='utf-8')
if __name__ == '__main__':
    main()
