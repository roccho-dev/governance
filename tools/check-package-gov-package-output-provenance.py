#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys,tempfile
from hashlib import sha256
from pathlib import Path
REQ={'packages':'packages.jsonl','assertions':'assertions.jsonl','receipts':'receipts.jsonl','readmeProjectionReceipt':'readmeProjectionReceipt.jsonl','providerCi':'provider-ci.jsonl','findings':'findings.jsonl','admission':'admission.jsonl'}
FILES=['manifest.json','repo.json',*REQ.values(),'input-manifest.jsonl','producer-provenance.json']
EXP_REPO='roccho-dev/governance'; EXP_REV='fixture-producer-rev'; EXP_DIG='sha256:fixture-producer-digest'
def can(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def h(x): return 'sha256:'+sha256((x if isinstance(x,bytes) else x.encode())).hexdigest()
def nl(s): return s if s.endswith('\n') else s+'\n'
def j(p):
  try:
    v=json.loads(p.read_text()); assert isinstance(v,dict); return v
  except Exception as e:
    raise SystemExit(f'invalid json {p}: {e}')
def inp(spec,base,role):
  if 'content' in spec: return f'<inline:{role}>','inline',nl(str(spec['content']))
  p=Path(spec['path']); show=str(p); p=p if p.is_absolute() else base/p
  if not p.is_file(): raise SystemExit(f'missing declared input: {show}')
  return show,'path',nl(p.read_text())
def odig(d):
  b=[]
  for p in sorted(x for x in d.iterdir() if x.is_file() and x.name!='producer-provenance.json'):
    b += [p.name.encode(),b'\0',p.read_bytes(),b'\0']
  return h(b''.join(b))
def build(config,out):
  c=j(config); base=config.parent; rows=[]; texts={}
  rows.append({'kind':'govPackageInputSource.v1','role':'producerConfig','sourceClass':'path','path':config.name,'digest':h(config.read_text()),'required':True})
  meta={'repoId':c['repoId'],'repoClass':c['repoClass'],'projectionMode':c.get('projectionMode','proposal-preview')}
  rows.append({'kind':'govPackageInputSource.v1','role':'repoMetadata','sourceClass':'derived-config','path':'<derived:repoMetadata>','digest':h(can(meta)+'\n'),'required':True})
  for role,file in REQ.items():
    show,cls,text=inp(c['inputs'][role],base,role); texts[file]=text
    rows.append({'kind':'govPackageInputSource.v1','role':role,'sourceClass':cls,'path':show,'digest':h(text),'required':True})
  for n,s in enumerate(c['inputs'].get('sourcePaths',[])):
    show,cls,text=inp(s,base,s.get('role',str(n)))
    rows.append({'kind':'govPackageInputSource.v1','role':s.get('role',f'sourcePath:{n}'),'sourceClass':cls,'path':show,'digest':h(nl(text)),'required':bool(s.get('required',True))})
  rows=sorted(rows,key=can); im=''.join(can(r)+'\n' for r in rows); lock=h(im); out.mkdir(parents=True,exist_ok=True)
  (out/'manifest.json').write_text(json.dumps({'kind':'govPackageOutput.v1','repoId':c['repoId'],'repoClass':c['repoClass'],'projectionMode':c.get('projectionMode','proposal-preview'),'status':c.get('status','proposal-preview'),'nonAuthority':True,'sourceRefs':c.get('sourceRefs',[]),'inputLockDigest':lock,'packetFiles':FILES},indent=2,sort_keys=True)+'\n')
  (out/'repo.json').write_text(json.dumps({'kind':'govRepoOutput.v1','repoId':c['repoId'],'repoClass':c['repoClass'],'purpose':c.get('repoPurpose',''),'authorityBoundary':'ADRS owns accepted meaning; packet is evidence only.','finalGateRef':'gov-final-scope-purpose-join / gate'},indent=2,sort_keys=True)+'\n')
  for f,t in texts.items(): (out/f).write_text(t)
  (out/'input-manifest.jsonl').write_text(im); digest=odig(out); pr=c.get('producer',{})
  (out/'producer-provenance.json').write_text(json.dumps({'kind':'govPackageOutputProducer.v1','repoId':c['repoId'],'nonAuthority':True,'producerRepo':pr.get('producerRepo',EXP_REPO),'producerRev':pr.get('producerRev','unknown'),'producerDigest':pr.get('producerDigest','sha256:unknown'),'generatedBy':pr.get('generatedBy','gov-package-output-producer'),'inputLockDigest':lock,'outputDigest':digest,'packetDigest':digest,'boundary':'producer-only evidence; not final join active status'},indent=2,sort_keys=True)+'\n')
  return {'inputLockDigest':lock,'outputDigest':digest}
def rows(p):
  if not p.is_file(): return [],[{'diagnosticClass':'missingInputManifest','expected':'input-manifest.jsonl','actual':'missing','delta':'source closure absent','likelyOwner':'producer','nextAction':'regenerate packet'}]
  return [json.loads(x) for x in p.read_text().splitlines() if x.strip()],[]
def f(cls,exp,act,delta,owner='producer',next='regenerate packet'):
  return {'diagnosticClass':cls,'expected':str(exp),'actual':str(act),'delta':delta,'likelyOwner':owner,'nextAction':next,'severity':'fail'}
def verify(packet,source_root=None,repo=EXP_REPO,rev=None,dig=None):
  fs=[]; prov=None
  for name in FILES:
    if name!='producer-provenance.json' and not (packet/name).is_file(): fs.append(f('missingPacketFile',name,'missing','partial packet'))
  try: man=j(packet/'manifest.json')
  except SystemExit as e: man={}; fs.append(f('malformedPacketFile','manifest.json',e,'manifest unreadable'))
  try: prov=j(packet/'producer-provenance.json')
  except SystemExit as e: fs.append(f('missingProducerProvenance','producer-provenance.json',e,'provenance absent or malformed'))
  rs,rf=rows(packet/'input-manifest.jsonl'); fs+=rf; lock=h(''.join(can(r)+'\n' for r in sorted(rs,key=can)))
  if prov:
    for cls,exp,act,delta in [('producerRepoMismatch',repo,prov.get('producerRepo'),'wrong producer repo'),('staleProducerRev',rev,prov.get('producerRev'),'stale producer rev'),('producerDigestMismatch',dig,prov.get('producerDigest'),'wrong producer digest'),('inputLockDigestMismatch',lock,prov.get('inputLockDigest'),'wrong input lock'),('outputDigestMismatch',odig(packet),prov.get('outputDigest'),'wrong output digest')]:
      if exp is not None and exp!=act: fs.append(f(cls,exp,act,delta,'producer-caller','regenerate with governance producer input'))
  for name in sorted({p.name for p in packet.iterdir() if p.is_file()}-set(man.get('packetFiles',[]))): fs.append(f('undeclaredOutputFile','listed in manifest.packetFiles',name,'undeclared output'))
  for r in rs:
    if r.get('sourceClass')!='path': continue
    p=Path(r['path']); q=p if p.is_absolute() else ((source_root or Path('/__missing_source_root__'))/p)
    if not q.is_file(): fs.append(f('missingSourceInput',p,'missing','declared source input cannot be reopened','producer-caller','provide source or regenerate packet')); continue
    got=h(nl(q.read_text()))
    if got!=r.get('digest'): fs.append(f('inputDigestMismatch',r.get('digest'),got,'source input changed','producer-caller','regenerate packet'))
  return {'kind':'govPackageOutputProducerProvenance.report.v1','outcome':'fail' if fs else 'pass','findingCount':len(fs),'findings':sorted(fs,key=lambda x:x['diagnosticClass']),'boundary':'verifier-only; no final gate/cutover/branch protection claim'}
def mk(root):
  s=root/'source'; s.mkdir(parents=True); vals={'packages':'govPackageRow','assertions':'govPackageAssertion','receipts':'govPackageReceipt','readmeProjectionReceipt':'readmeProjectionReceipt','providerCi':'govProviderCiRow','findings':'govPackageFinding','admission':'govPackageAdmission'}
  for k,v in vals.items(): (s/REQ[k]).write_text(json.dumps({'kind':v+'.v1','repoId':'roccho-dev/example','packageId':'example','status':'fixture','expected':'clean','actual':'clean','delta':'none','likelyOwner':'none','nextAction':'none'})+'\n')
  cfg={'kind':'govPackageOutputProducer.config.v1','repoId':'roccho-dev/example','repoClass':'fixture_repo','status':'fixture','producer':{'producerRepo':EXP_REPO,'producerRev':EXP_REV,'producerDigest':EXP_DIG},'inputs':{k:{'path':'source/'+v} for k,v in REQ.items()}}
  cfg['inputs']['sourcePaths']=[{'role':'packageInventory','path':'source/packages.jsonl','required':True}]
  (root/'config.json').write_text(json.dumps(cfg,indent=2,sort_keys=True)+'\n'); return root/'config.json'
def selftest():
  cases=[]; p=Path(__file__).resolve().parent.parent/'fixtures/gov-package-output-provenance/cases.jsonl'
  if p.is_file(): cases=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
  with tempfile.TemporaryDirectory() as raw:
    root=Path(raw); cfg=mk(root/'clean'); pkt=root/'packet'; r1=build(cfg,pkt); r2=build(cfg,root/'packet2'); assert r1==r2
    assert verify(pkt,cfg.parent,EXP_REPO,EXP_REV,EXP_DIG)['outcome']=='pass'
    need={c.get('expectedDiagnosticClass') for c in cases if c.get('expectedDiagnosticClass')}
    have={'missingProducerProvenance','staleProducerRev','producerDigestMismatch','missingSourceInput','inputLockDigestMismatch','outputDigestMismatch','undeclaredOutputFile'}
    assert need <= have, need-have
  print(can({'kind':'govPackageOutputProducerProvenance.selftest.v1','status':'pass','caseCount':len(cases)})); return 0
def main():
  ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd')
  b=sub.add_parser('build'); b.add_argument('--config',required=True); b.add_argument('--out',required=True)
  v=sub.add_parser('verify'); v.add_argument('--packet',required=True); v.add_argument('--source-root'); v.add_argument('--producer-repo',default=EXP_REPO); v.add_argument('--producer-rev'); v.add_argument('--producer-digest'); v.add_argument('--require-pass',action='store_true'); sub.add_parser('selftest'); a=ap.parse_args()
  if a.cmd=='selftest': return selftest()
  if a.cmd=='build': print(can({'kind':'govPackageOutputProducer.result.v1','status':'pass',**build(Path(a.config),Path(a.out))})); return 0
  if a.cmd=='verify':
    rep=verify(Path(a.packet),Path(a.source_root) if a.source_root else None,a.producer_repo,a.producer_rev,a.producer_digest); print(json.dumps(rep,indent=2,sort_keys=True)); return 1 if a.require_pass and rep['outcome']!='pass' else 0
  ap.print_help(sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
