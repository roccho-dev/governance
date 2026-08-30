#!/usr/bin/env python3
"""Compile one content-addressed organization snapshot into the six #331 lanes."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,re,tempfile
from pathlib import Path
from typing import Any
LANES={'contractGraph':'contractGraph.current.v1','decisionImpact':'decisionImpact.current.v1','obligationState':'obligationState.current.v1','workCurrent':'workLifecycle.current.v1','responsibilityClosure':'responsibilityClosure.current.v1','evidenceState':'evidenceState.current.v1'}
KINDS={'organizationMap.meta.v1','organizationMap.repositorySnapshot.v1','organizationMap.decision.v1','organizationMap.obligation.v1','organizationMap.work.v1','organizationMap.factorySpine.v1'}
SHA=re.compile(r'^[0-9a-f]{40}$')
class ContractError(ValueError): pass
def can(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def db(b:bytes)->str:return 'sha256:'+hashlib.sha256(b).hexdigest()
def dv(v:Any)->str:return db(can(v).encode())
def rowsort(rows):return sorted(rows,key=lambda r:(str(r.get('id','')),str(r.get('kind','')),can(r)))
def string(r,k):
 v=r.get(k)
 if not isinstance(v,str) or not v: raise ContractError(f"{r.get('id','?')}: {k} required")
 return v
def read(path:Path):
 raw=path.read_bytes()
 if raw.startswith(b'\xef\xbb\xbf') or b'\r' in raw: raise ContractError('source must be UTF-8 LF without BOM')
 rows=[]
 for n,line in enumerate(raw.decode().split('\n'),1):
  if not line.strip():continue
  try:r=json.loads(line)
  except json.JSONDecodeError as e:raise ContractError(f'line {n}: invalid JSON: {e}') from e
  if not isinstance(r,dict):raise ContractError(f'line {n}: object required')
  rows.append(r)
 if not rows:raise ContractError('source empty')
 return raw,rows
def validate(rows):
 ids={}; repos={}; entities=set()
 for r in rows:
  kind=string(r,'kind'); ident=string(r,'id')
  if kind not in KINDS:raise ContractError(f'unsupported kind: {kind}')
  if ident in ids:raise ContractError(f'duplicate id: {ident}')
  if r.get('authority') is not False:raise ContractError(f'{ident}: authority=false required')
  ids[ident]=r;entities.add(ident)
 for r in rows:
  if r['kind']!='organizationMap.repositorySnapshot.v1':continue
  repo=string(r,'repoId');rev=string(r,'sourceRev')
  if repo in repos:raise ContractError(f'duplicate repository: {repo}')
  if not SHA.fullmatch(rev):raise ContractError(f'{r["id"]}: exact sourceRev required')
  if r.get('inventoryState') not in {'observed','unknown'}:raise ContractError(f'{r["id"]}: invalid inventoryState')
  for field in ('packages','requiredPackageExpectations'):
   values=r.get(field)
   if not isinstance(values,list) or any(not isinstance(x,str) or not x for x in values):raise ContractError(f'{r["id"]}: {field} must be string[]')
   if values!=sorted(set(values)):raise ContractError(f'{r["id"]}: {field} must be sorted and unique')
  if r.get('packageCount')!=len(r['packages']):raise ContractError(f'{r["id"]}: package count mismatch')
  if r.get('requiredPackageExpectationCount')!=len(r['requiredPackageExpectations']):raise ContractError(f'{r["id"]}: required expectation count mismatch')
  if r['inventoryState']=='observed' and not r['packages']:raise ContractError(f'{r["id"]}: observed inventory empty')
  if r['inventoryState']=='unknown' and r['packages']:raise ContractError(f'{r["id"]}: unknown inventory contains packages')
  repos[repo]=r
  entities.update(f'package:{repo}:{x}' for x in r['packages'])
  entities.update(f'requirement:{repo}:{x}' for x in r['requiredPackageExpectations'])
 if not repos:raise ContractError('no repository snapshots')
 metas=[r for r in rows if r['kind']=='organizationMap.meta.v1']
 if len(metas)!=1:raise ContractError('exactly one meta row required')
 accepted=[r for r in rows if r['kind']=='organizationMap.decision.v1' and r.get('status')=='accepted']
 if not accepted:raise ContractError('accepted decision required')
 for r in accepted:
  if not SHA.fullmatch(string(r,'acceptedCommit')):raise ContractError(f'{r["id"]}: exact acceptedCommit required')
 for r in rows:
  if r['kind'] in {'organizationMap.obligation.v1','organizationMap.work.v1'}:
   repo=string(r,'ownerRepoId' if r['kind']=='organizationMap.obligation.v1' else 'repoId')
   if repo not in repos:raise ContractError(f'{r["id"]}: unknown repo {repo}')
  if r['kind']=='organizationMap.factorySpine.v1':
   steps=r.get('steps')
   if not isinstance(steps,list) or not steps:raise ContractError(f'{r["id"]}: nonempty steps required')
   for i,s in enumerate(steps):
    if not isinstance(s,dict):raise ContractError(f'{r["id"]}.steps[{i}]: object required')
    a=string(s,'from');b=string(s,'to');string(s,'label')
    missing=sorted(x for x in (a,b) if x not in entities)
    if missing:raise ContractError(f'{r["id"]}.steps[{i}]: dangling endpoint {missing}')
 return repos
def lane(kind,sd,**fields):return {'kind':kind,'authority':False,'sourceDigest':sd,**fields}
def compile(rows,sd):
 repos=validate(rows);by={}
 for r in rows:by.setdefault(r['kind'],[]).append(r)
 graph=[];closures=[];evidence=[]
 for repo,s in sorted(repos.items()):
  observed=set(s['packages'])
  graph.append({'id':s['id'],'entityKind':'repository','repoId':repo,'repoClass':s['repoClass'],'sourceRev':s['sourceRev'],'sourceRef':s['sourceRef'],'inventoryState':s['inventoryState'],'authority':False})
  for p in s['packages']:
   graph.append({'id':f'package:{repo}:{p}','entityKind':'package','repoId':repo,'packageId':p,'packagePath':f'{s["packageRoot"]}/{p}','sourceRev':s['sourceRev'],'sourceRef':f'{s["sourceRef"]}/{s["packageRoot"]}/{p}','status':'observed','authority':False})
  for p in s['requiredPackageExpectations']:
   status='observed-match' if p in observed else 'missing-or-unmatched'
   graph.append({'id':f'requirement:{repo}:{p}','entityKind':'required-package-expectation','repoId':repo,'packageId':p,'contractRef':s['requiredContractRef'],'contractState':'proposed-target','status':status,'authority':False})
  closures.append({'id':f'closure:{s["id"]}','repoId':repo,'inventoryState':s['inventoryState'],'observedPackageCount':len(s['packages']),'requiredExpectationCount':len(s['requiredPackageExpectations']),'status':'observed' if s['inventoryState']=='observed' else 'unknown','authority':False})
  evidence.append({'id':f'evidence:{s["id"]}','repoId':repo,'sourceRev':s['sourceRev'],'sourceRef':s['sourceRef'],'status':'readback','authority':False})
 graph.sort(key=lambda r:r['id']);closures.sort(key=lambda r:r['id']);evidence.sort(key=lambda r:r['id'])
 decisions=rowsort(by.get('organizationMap.decision.v1',[]));obligations=rowsort(by.get('organizationMap.obligation.v1',[]));spines=rowsort(by.get('organizationMap.factorySpine.v1',[]));works=rowsort(by.get('organizationMap.work.v1',[]))
 return {
  'contractGraph':lane(LANES['contractGraph'],sd,repositories=[s for _,s in sorted(repos.items())],entities=graph,spines=spines),
  'decisionImpact':lane(LANES['decisionImpact'],sd,decisions=decisions,obligations=obligations),
  'obligationState':lane(LANES['obligationState'],sd,rows=obligations),
  'workCurrent':lane(LANES['workCurrent'],sd,rows=works),
  'responsibilityClosure':lane(LANES['responsibilityClosure'],sd,rows=closures),
  'evidenceState':lane(LANES['evidenceState'],sd,rows=evidence),
 }
def binder(path):
 spec=importlib.util.spec_from_file_location('bundle_binder',path)
 if spec is None or spec.loader is None:raise ContractError(f'cannot load binder: {path}')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def build(source,binder_path,decision_ref):
 raw,rs=read(source);sd=db(raw);states=compile(rs,sd);m=binder(binder_path)
 with tempfile.TemporaryDirectory() as td:
  inputs={};sources={};expects={}
  for role in sorted(states):
   p=Path(td)/f'{role}.json';data=(can(states[role])+'\n').encode();p.write_bytes(data)
   inputs[role]=p;sources[role]=f'source://internal-organization-map@{sd}#{role}';expects[role]=db(data)
  bundle=m.build_bundle(decision_ref=decision_ref,inputs=inputs,sources=sources,expected_digests=expects)
 repo_count=sum(r['kind']=='organizationMap.repositorySnapshot.v1' for r in rs)
 package_count=sum(len(r.get('packages',[])) for r in rs if r['kind']=='organizationMap.repositorySnapshot.v1')
 required_count=sum(len(r.get('requiredPackageExpectations',[])) for r in rs if r['kind']=='organizationMap.repositorySnapshot.v1')
 gap_count=sum(r['kind']=='organizationMap.repositorySnapshot.v1' and r['inventoryState']=='unknown' for r in rs)
 receipt={'kind':'governance.internalOrganizationMapBuildReceipt.v1','authority':False,'status':'PASS','decisionRef':decision_ref,'sourceDigest':sd,'bundleSemanticDigest':bundle['semanticDigest'],'bundleBytesDigest':db((can(bundle)+'\n').encode()),'laneDigests':{x['role']:x['digest'] for x in bundle['inputs']},'counts':{'sourceRows':len(rs),'repositories':repo_count,'observedPackages':package_count,'requiredPackageExpectations':required_count,'explicitInventoryGaps':gap_count},'claimCeiling':'bounded observation; not all-package conformance, deployment, production, or business outcome'}
 return bundle,receipt
def write(path,v):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(can(v)+'\n',encoding='utf-8',newline='\n')
def minimal():
 rev='a'*40
 return rowsort([
  {'kind':'organizationMap.meta.v1','id':'organization:test','authority':False,'title':'test','status':'current'},
  {'kind':'organizationMap.repositorySnapshot.v1','id':'repo:roccho-dev/test','authority':False,'repoId':'roccho-dev/test','repoClass':'test','sourceRev':rev,'sourceRef':'https://example.invalid/test','packageRoot':'packages','inventoryState':'observed','packages':['alpha'],'packageCount':1,'requiredPackageExpectations':['alpha'],'requiredPackageExpectationCount':1,'requiredContractRef':'https://example.invalid/contract','status':'observed'},
  {'kind':'organizationMap.decision.v1','id':'decision:test','authority':False,'decisionRef':'https://example.invalid/decision','acceptedCommit':rev,'status':'accepted','title':'test'},
  {'kind':'organizationMap.obligation.v1','id':'obligation:test','authority':False,'decisionId':'decision:test','ownerRepoId':'roccho-dev/test','title':'build','status':'pending','sourceRef':'https://example.invalid/decision'},
  {'kind':'organizationMap.work.v1','id':'work:test','authority':False,'repoId':'roccho-dev/test','sourceRef':'https://example.invalid/work','status':'pending'},
  {'kind':'organizationMap.factorySpine.v1','id':'spine:test','authority':False,'steps':[{'from':'decision:test','to':'obligation:test','label':'requires'},{'from':'obligation:test','to':'requirement:roccho-dev/test:alpha','label':'requires'},{'from':'requirement:roccho-dev/test:alpha','to':'package:roccho-dev/test:alpha','label':'matches'}]},
 ])
def fails(fragment,rows,cases):
 try:compile(rows,dv(rows))
 except ContractError as e:
  if fragment not in str(e):raise AssertionError(f'expected {fragment!r}, got {e!r}') from e
  cases.append(fragment);return
 raise AssertionError(f'expected failure: {fragment}')
def selftest(binder_path):
 cases=[];clean=minimal();a=compile(clean,dv(clean));b=compile(list(reversed(clean)),dv(clean));assert can(a)==can(b);cases+=['clean','reordered-input']
 fails('duplicate id',clean+[dict(clean[0])],cases)
 bad=[dict(r) for r in clean];next(r for r in bad if r['kind']=='organizationMap.factorySpine.v1')['steps']=[{'from':'decision:test','to':'package:missing','label':'feeds'}];fails('dangling endpoint',bad,cases)
 bad=[dict(r) for r in clean];next(r for r in bad if r['kind']=='organizationMap.repositorySnapshot.v1')['sourceRev']='short';fails('exact sourceRev',bad,cases)
 bad=[dict(r) for r in clean];next(r for r in bad if r['kind']=='organizationMap.repositorySnapshot.v1')['packages']=[];fails('package count mismatch',bad,cases)
 bad=[dict(r) for r in clean];bad[0]['authority']=True;fails('authority=false',bad,cases)
 m=binder(binder_path)
 with tempfile.TemporaryDirectory() as td:
  inputs={};sources={};expects={}
  for role,v in a.items():
   p=Path(td)/f'{role}.json';data=(can(v)+'\n').encode();p.write_bytes(data);inputs[role]=p;sources[role]=f'fixture://{role}';expects[role]=db(data)
  bundle=m.build_bundle(decision_ref='https://github.com/roccho-dev/adrs/issues/331',inputs=inputs,sources=sources,expected_digests=expects)
  assert bundle['kind']=='controlSurface.bundle.v1' and bundle['authority'] is False
 cases.append('accepted-binder')
 print(can({'kind':'governance.internalOrganizationMap.selftest.v1','authority':False,'status':'PASS','caseCount':len(cases),'cases':cases}));return 0
def main():
 p=argparse.ArgumentParser();c=p.add_subparsers(dest='cmd',required=True);s=c.add_parser('selftest');s.add_argument('--binder',type=Path,default=Path(__file__).with_name('build-control-surface-bundle.py'));b=c.add_parser('build');b.add_argument('--source',type=Path,required=True);b.add_argument('--binder',type=Path,default=Path(__file__).with_name('build-control-surface-bundle.py'));b.add_argument('--decision-ref',default='https://github.com/roccho-dev/adrs/issues/331');b.add_argument('--out',type=Path,required=True);b.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
 try:
  if a.cmd=='selftest':return selftest(a.binder)
  bundle,receipt=build(a.source,a.binder,a.decision_ref);write(a.out,bundle);write(a.receipt,receipt);print(can(receipt));return 0
 except ContractError as e:raise SystemExit(f'internal-organization-map: {e}') from e
if __name__=='__main__':raise SystemExit(main())
