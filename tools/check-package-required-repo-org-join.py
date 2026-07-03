#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,shutil,sys,tempfile
from hashlib import sha256
from pathlib import Path
REQ_REPO=['repoId','repoClass','requiredOutput','requiredProducer','enforcementMode','effectiveFrom','owner']
REQ_REG=['repoId','sourceKind','sourceRepo','sourceRev','packetPath','packetDigest','producerRev','freshness']
PACKET_FILES=['manifest.json','repo.json','packages.jsonl','assertions.jsonl','receipts.jsonl','readmeProjectionReceipt.jsonl','provider-ci.jsonl','findings.jsonl','admission.jsonl','producer-provenance.json']
CLASSES={'projection_gate','authority_records','effectful_executor','renderer','feature_repo'}
def can(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def h(b): return 'sha256:'+sha256(b if isinstance(b,bytes) else b.encode()).hexdigest()
def read_jsonl(p):
  rows=[]
  for n,l in enumerate(p.read_text().splitlines(),1):
    if not l.strip(): continue
    try:
      r=json.loads(l); assert isinstance(r,dict); rows.append(r)
    except Exception as e:
      rows.append({'kind':'_malformed','repoId':'*','_line':n,'_error':str(e)})
  return rows
def write_jsonl(p,rows): p.write_text(''.join(can(r)+'\n' for r in rows))
def finding(repo,cls,exp,act,delta,owner='governance',nxt='fix source input and rerun join',**kw):
  r={'kind':'govPackageOutputFinding.v1','repoId':repo,'diagnosticClass':cls,'expected':str(exp),'actual':str(act),'delta':delta,'likelyOwner':owner,'nextAction':nxt,'severity':'blocking'}; r.update(kw); return r
def compile_universe(path):
  out=[]; fs=[]; seen={}
  for r in read_jsonl(path):
    repo=r.get('repoId','*')
    if r.get('kind')=='_malformed': fs.append(finding(repo,'malformedRequiredRepoRow','JSON object',r.get('_error'),'row cannot be parsed')); continue
    if r.get('kind')!='govRequiredRepo.v1': continue
    miss=[k for k in REQ_REPO if not r.get(k)]
    if miss: fs.append(finding(repo,'missingRequiredRepoField',REQ_REPO,miss,'required repo row incomplete','adrs','add required field in accepted ADRS input'))
    if r.get('repoClass') and r.get('repoClass') not in CLASSES: fs.append(finding(repo,'unknownRepoClass',sorted(CLASSES),r.get('repoClass'),'repoClass unsupported','adrs','use accepted repoClass'))
    if repo in seen: fs.append(finding(repo,'duplicateRequiredRepoId','one row per repoId',repo,'duplicate required repo row','adrs','deduplicate accepted rows'))
    seen[repo]=True; out.append({k:r.get(k) for k in REQ_REPO})
  return sorted(out,key=lambda x:x.get('repoId','')),sorted(fs,key=can)
def compile_registry(path):
  out=[]; fs=[]; seen={}
  for r in read_jsonl(path):
    repo=r.get('repoId','*')
    if r.get('kind')=='_malformed': fs.append(finding(repo,'malformedPacketRegistryRow','JSON object',r.get('_error'),'row cannot be parsed')); continue
    if r.get('kind')!='govPackagePacketSource.v1': continue
    miss=[k for k in REQ_REG if not r.get(k)]
    if miss: fs.append(finding(repo,'missingPacketSourceField',REQ_REG,miss,'packet source row incomplete','governance','add pinned packet source row'))
    if not r.get('sourceRev') or not r.get('packetDigest'): fs.append(finding(repo,'unpinnedPacketSource','sourceRev and packetDigest',r,'mutable packet source','governance','pin packet source revision and digest'))
    if repo in seen: fs.append(finding(repo,'duplicatePacketSource','one packet source per repoId',repo,'duplicate packet source row','governance','deduplicate registry'))
    seen[repo]=True; out.append({k:r.get(k) for k in REQ_REG})
  return sorted(out,key=lambda x:x.get('repoId','')),sorted(fs,key=can)
def packet_digest(path):
  b=[]
  for p in sorted(x for x in path.iterdir() if x.is_file() and x.name!='producer-provenance.json'):
    b += [p.name.encode(),b'\0',p.read_bytes(),b'\0']
  return h(b''.join(b))
def jfile(p):
  try:
    v=json.loads(p.read_text()); assert isinstance(v,dict); return v,None
  except Exception as e: return {},str(e)
def packet_findings(universe,registry,packet_root):
  fs=[]; by={r['repoId']:r for r in registry if r.get('repoId')}
  for u in universe:
    repo=u['repoId']; r=by.get(repo)
    if not r: fs.append(finding(repo,'missingPacketSource','packet registry row','missing','required repo has no packet source','governance','add packet registry row')); continue
    path=packet_root/r['packetPath']
    if not path.exists(): fs.append(finding(repo,'missingGovPackageOutput',r['packetPath'],'missing','packet path unavailable','repo-owner','publish govPackageOutput packet')); continue
    if not path.is_dir(): fs.append(finding(repo,'unavailableGovPackageOutput','directory packet',r['packetPath'],'packet locator is not a directory','repo-owner','publish readable packet')); continue
    for name in PACKET_FILES:
      if not (path/name).is_file(): fs.append(finding(repo,'malformedGovPackageOutput',name,'missing','required packet file absent','repo-owner','regenerate packet'))
    man,em=jfile(path/'manifest.json'); prov,ep=jfile(path/'producer-provenance.json')
    if em: fs.append(finding(repo,'malformedGovPackageOutput','valid manifest.json',em,'manifest unreadable','repo-owner','regenerate packet'))
    if ep: fs.append(finding(repo,'missingProducerProvenance','producer-provenance.json',ep,'producer provenance absent or unreadable','repo-owner','regenerate with governance producer'))
    if man and man.get('kind')!='govPackageOutput.v1': fs.append(finding(repo,'unsupportedPacketSchema','govPackageOutput.v1',man.get('kind'),'unsupported packet kind','repo-owner','emit accepted packet schema'))
    if man and man.get('repoId')!=repo: fs.append(finding(repo,'packetRepoMismatch',repo,man.get('repoId'),'packet belongs to another repo','repo-owner','use matching packet'))
    expected_rev=(r.get('freshness') or {}).get('expectedSourceRev')
    if expected_rev and r.get('sourceRev')!=expected_rev: fs.append(finding(repo,'stalePacketSourceRev',expected_rev,r.get('sourceRev'),'packet source revision stale','repo-owner','refresh pinned packet source'))
    got=packet_digest(path)
    if str(r.get('packetDigest','')).startswith('sha256:') and r.get('packetDigest')!=got: fs.append(finding(repo,'packetDigestMismatch',r.get('packetDigest'),got,'registry digest does not match packet','governance','update registry digest after verification',packetDigest=got))
    if prov:
      if prov.get('producerRepo')!=u.get('requiredProducer'): fs.append(finding(repo,'producerRepoMismatch',u.get('requiredProducer'),prov.get('producerRepo'),'packet produced by unexpected producer','repo-owner','regenerate with required producer'))
      if r.get('producerRev') and prov.get('producerRev')!=r.get('producerRev'): fs.append(finding(repo,'producerRevMismatch',r.get('producerRev'),prov.get('producerRev'),'producer revision does not match registry','repo-owner','pin matching producer revision'))
      if prov.get('outputDigest') and prov.get('outputDigest')!=got: fs.append(finding(repo,'outputDigestMismatch',prov.get('outputDigest'),got,'producer output digest mismatch','repo-owner','regenerate packet'))
  return sorted(fs,key=can)
def org_join(universe,registry,finds):
  fs_by={}
  for f in finds: fs_by.setdefault(f['repoId'],[]).append(f)
  required={u['repoId'] for u in universe}; out=[]
  for r in registry:
    if r.get('repoId') not in required: out.append(finding(r.get('repoId','*'),'orphanPacketSource','required repo universe',r.get('repoId'),'packet source for unrequired repo','governance','remove registry row or add accepted required repo row'))
  for u in universe:
    repo=u['repoId']
    if fs_by.get(repo):
      out.extend(fs_by[repo])
    else:
      out.append({'kind':'govOrgPackageOutput.v1','repoId':repo,'admission':'organization-active','status':'active','source':'required-repo-universe x packet-registry x packet-findings','boundary':'org join precursor only; not final gate or branch protection'})
  return sorted(out,key=lambda x:(x.get('repoId',''),x.get('diagnosticClass','')))
def run(universe_p,registry_p,packet_root,strict=False):
  uni,uf=compile_universe(universe_p); reg,rf=compile_registry(registry_p); pf=packet_findings(uni,reg,packet_root); out=org_join(uni,reg,uf+rf+pf)
  blocking=[x for x in out if x.get('severity')=='blocking']
  rep={'kind':'govRequiredRepoPacketOrgJoin.report.v1','outcome':'fail' if blocking else 'pass','universe':uni,'registry':reg,'rows':out,'blockingCount':len(blocking),'boundary':'D1-D4 evidence only; no final gate/cutover claim'}
  return rep, (1 if strict and blocking else 0)
def make_packet(path,repo,producer='roccho-dev/governance',rev='rev-ok'):
  path.mkdir(parents=True,exist_ok=True)
  for name in PACKET_FILES:
    if name.endswith('.jsonl'): (path/name).write_text('{"kind":"row.v1","repoId":"'+repo+'"}\n')
  (path/'manifest.json').write_text(json.dumps({'kind':'govPackageOutput.v1','repoId':repo},sort_keys=True)+'\n')
  (path/'repo.json').write_text(json.dumps({'kind':'govRepoOutput.v1','repoId':repo},sort_keys=True)+'\n')
  d=packet_digest(path)
  (path/'producer-provenance.json').write_text(json.dumps({'kind':'govPackageOutputProducer.v1','producerRepo':producer,'producerRev':rev,'outputDigest':d},sort_keys=True)+'\n')
  return d
def prepare_clean(root):
  fixture=Path(__file__).resolve().parent.parent/'fixtures/required-repo-org-join/clean'
  shutil.copytree(fixture,root,dirs_exist_ok=True)
  pkt=root/'packets'; gd=make_packet(pkt/'governance','roccho-dev/governance'); ad=make_packet(pkt/'adrs','roccho-dev/adrs')
  rows=read_jsonl(root/'registry.jsonl')
  for r in rows:
    if r['repoId']=='roccho-dev/governance': r['packetDigest']=gd
    if r['repoId']=='roccho-dev/adrs': r['packetDigest']=ad
  write_jsonl(root/'registry.jsonl',rows)
def selftest():
  cases=[json.loads(x) for x in (Path(__file__).resolve().parent.parent/'fixtures/required-repo-org-join/cases.jsonl').read_text().splitlines() if x.strip()]
  with tempfile.TemporaryDirectory() as raw:
    base=Path(raw)
    for c in cases:
      root=base/c['caseId']; prepare_clean(root)
      if c['caseId']=='missing-required-field':
        rows=read_jsonl(root/'universe.jsonl'); rows[0].pop('owner'); write_jsonl(root/'universe.jsonl',rows)
      elif c['caseId']=='duplicate-required-repo':
        rows=read_jsonl(root/'universe.jsonl'); rows.append(rows[0]); write_jsonl(root/'universe.jsonl',rows)
      elif c['caseId']=='unknown-repo-class':
        rows=read_jsonl(root/'universe.jsonl'); rows[0]['repoClass']='unknown'; write_jsonl(root/'universe.jsonl',rows)
      elif c['caseId']=='missing-packet-source':
        rows=[r for r in read_jsonl(root/'registry.jsonl') if r['repoId']!='roccho-dev/adrs']; write_jsonl(root/'registry.jsonl',rows)
      elif c['caseId']=='unpinned-source':
        rows=read_jsonl(root/'registry.jsonl'); rows[0]['sourceRev']=''; write_jsonl(root/'registry.jsonl',rows)
      elif c['caseId']=='missing-packet': shutil.rmtree(root/'packets/adrs')
      elif c['caseId']=='stale-packet':
        rows=read_jsonl(root/'registry.jsonl'); rows[0]['sourceRev']='old'; rows[0]['freshness']['expectedSourceRev']='new'; write_jsonl(root/'registry.jsonl',rows)
      elif c['caseId']=='malformed-packet': (root/'packets/adrs/manifest.json').write_text('{bad')
      elif c['caseId']=='invalid-provenance':
        p=root/'packets/adrs/producer-provenance.json'; v=json.loads(p.read_text()); v['producerRev']='wrong'; p.write_text(json.dumps(v)+'\n')
      rep,code=run(root/'universe.jsonl',root/'registry.jsonl',root/'packets',True)
      assert rep['outcome']==c['expectedOutcome'],(c,rep)
      if c.get('expectedDiagnosticClass'):
        assert c['expectedDiagnosticClass'] in {x.get('diagnosticClass') for x in rep['rows']},(c,rep)
  print(can({'kind':'govRequiredRepoPacketOrgJoin.selftest.v1','status':'pass','caseCount':len(cases)})); return 0
def main():
  ap=argparse.ArgumentParser(); ap.add_argument('cmd',choices=['check','selftest']); ap.add_argument('--universe'); ap.add_argument('--registry'); ap.add_argument('--packet-root'); ap.add_argument('--strict',action='store_true'); a=ap.parse_args()
  if a.cmd=='selftest': return selftest()
  rep,code=run(Path(a.universe),Path(a.registry),Path(a.packet_root),a.strict); print(json.dumps(rep,indent=2,sort_keys=True)); return code
if __name__=='__main__': raise SystemExit(main())
