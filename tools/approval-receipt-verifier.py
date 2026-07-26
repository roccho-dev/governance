#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_VERSION="approval-receipt-verifier.v1"
PACKAGE_IDENTITY="nix:approval-receipt-verifier"
SCHEMA_DIGESTS={
 "authorityGrant.v1":"sha256:a0c52c668cd0267ee6187fa3f84a79ce6bd8d6a5e76b4e1d433ee976a8d60cab",
 "githubApprovalEvidence.v1":"sha256:afd88be8835b4294195050eb0354fa97361778de2dda07728f36a44587292e80",
 "approvalReceipt.v1":"sha256:d3d52f076a94dce2693827aebecae7fdc18d5345bd2e0be39c85f090bc028ff4",
 "implementationManifest.v1":"sha256:e264ffc287eb4adcdf4b2ee6e5b2194300dd76963f913fec511e387ac5663957",
}
VALID,INVALID,ERROR="VALID","INVALID","ERROR"
Json=dict[str,Any]
GRANT_KEYS={"kind","grant_id","subject_id","action_kinds","resource_scope","provider_bindings","valid_from","valid_until","status"}
SCOPE_KEYS={"repository","subject_kind","finding_digest","policy_digest","candidate_revision","provider_object_ids"}
OBJECT_KEYS={"repository_id","pull_request_number","pull_request_id"}
BINDING_KEYS={"provider","provider_account_id","provider_login"}
EVIDENCE_KEYS={
 "kind","provider","repository_id","repository_full_name","pull_request_number","pull_request_id",
 "candidate_revision","review_id","review_commit_id","review_state","review_submitted_at",
 "review_dismissed","actor_account_id","actor_login","actor_type","observed_at",
 "provider_response_digest","adapter_manifest_digest","status","findings","claim_ceiling",
}
SUBJECT_KEYS={"repository","candidate_revision","finding_digest","policy_digest"}
MANIFEST_KEYS={"kind","component","version","source_files","schema_digests","package_identity","manifest_digest"}
CODES={
"ACTOR_BINDING_MISSING","ACTOR_PROVIDER_ID_MISMATCH","ACTOR_LOGIN_MISMATCH",
"AUTHORITY_GRANT_MISSING","AUTHORITY_GRANT_DUPLICATE","AUTHORITY_GRANT_INACTIVE",
"AUTHORITY_GRANT_EXPIRED","AUTHORITY_SCOPE_MISMATCH","ACTION_KIND_NOT_GRANTED",
"CANDIDATE_REVISION_MISMATCH","REVIEW_COMMIT_MISMATCH","SUBJECT_DIGEST_MISMATCH",
"POLICY_DIGEST_MISMATCH","REVIEW_STATE_NOT_APPROVED","REVIEW_DISMISSED",
"PROVIDER_EVIDENCE_MALFORMED","PROVIDER_EVIDENCE_DIGEST_MISMATCH",
"PROVIDER_OBJECT_ID_MISMATCH","ACTION_TIME_OUTSIDE_GRANT","AS_OF_MISSING",
"ENGINE_UNKNOWN","VALIDATION_EXCEPTION"}

def canonical(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def digest(v:Any)->str:return "sha256:"+hashlib.sha256(canonical(v).encode()).hexdigest()
def file_digest(path:Path)->str:return "sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()
def source_path()->Path:return Path(__file__).resolve()
def ceiling()->Json:
 return {"physical_human_identity_proven":False,"account_non_compromise_proven":False,"provider_independent_non_repudiation_proven":False}
def engine_manifest()->Json:
 return {"kind":"approvalVerifierEngineManifest.v1","component":"governance.approval-receipt-verifier","version":ENGINE_VERSION,"source_files":[{"path":"tools/approval-receipt-verifier.py","sha256":file_digest(source_path())}],"schema_digests":SCHEMA_DIGESTS,"package_identity":PACKAGE_IDENTITY}
def engine_manifest_digest()->str:return digest(engine_manifest())
def when(v:Any,name:str)->datetime:
 if not isinstance(v,str) or not v:raise ValueError(f"{name}: required")
 dt=datetime.fromisoformat(v.replace("Z","+00:00"))
 if dt.tzinfo is None:raise ValueError(f"{name}: timezone required")
 return dt.astimezone(timezone.utc)
def closed(v:Any,keys:set[str],name:str)->Json:
 if not isinstance(v,dict):raise ValueError(f"{name}: object required")
 unknown=set(v)-keys
 if unknown:raise ValueError(f"{name}: unknown keys {sorted(unknown)}")
 missing=keys-set(v)
 if missing:raise ValueError(f"{name}: missing keys {sorted(missing)}")
 return v
def finding(code:str,expected:Any,actual:Any,owner:str,next_action:str)->Json:
 assert code in CODES
 return {"code":code,"expected":expected,"actual":actual,"owner":owner,"next_action":next_action}
def error(subject:Any,as_of:Any,code:str,actual:Any)->Json:
 return {"kind":"approvalReceipt.v1","approval_id":None,"subject":subject if isinstance(subject,dict) else None,"actor":None,"action":None,"authority":None,"provider_evidence_digest":None,"engine_manifest_digest":engine_manifest_digest(),"as_of":as_of,"status":ERROR,"findings":[finding(code,"valid closed input",actual,"governance","repair input and rerun")],"claim_ceiling":ceiling()}

def validate_manifest(identity:Json)->bool:
 identity=closed(identity,MANIFEST_KEYS,"engine_identity")
 supplied_digest=identity.pop("manifest_digest")
 return identity==engine_manifest() and supplied_digest==engine_manifest_digest()

def validate_grant(grant:Any,index:int)->Json:
 g=closed(copy.deepcopy(grant),GRANT_KEYS,f"authority_grants[{index}]")
 if g.get("kind")!="authorityGrant.v1":raise ValueError(f"authority_grants[{index}]: kind")
 scope=closed(g.get("resource_scope"),SCOPE_KEYS,f"authority_grants[{index}].resource_scope")
 closed(scope.get("provider_object_ids"),OBJECT_KEYS,f"authority_grants[{index}].provider_object_ids")
 bindings=g.get("provider_bindings")
 if not isinstance(bindings,list) or len(bindings)!=1:raise ValueError(f"authority_grants[{index}].provider_bindings")
 closed(bindings[0],BINDING_KEYS,f"authority_grants[{index}].provider_bindings[0]")
 return g

def validate_approval(authority_grants:list[Json],github_evidence:Json,subject:Json,as_of:str|None,engine_identity:Json)->Json:
 """Pure provider-neutral evaluator: no I/O, network, environment, or implicit time."""
 try:
  if not as_of:return error(subject,as_of,"AS_OF_MISSING",as_of)
  as_of_dt=when(as_of,"as_of")
  subject=closed(copy.deepcopy(subject),SUBJECT_KEYS,"subject")
  ev=closed(copy.deepcopy(github_evidence),EVIDENCE_KEYS,"github_evidence")
  if not validate_manifest(copy.deepcopy(engine_identity)):return error(subject,as_of,"ENGINE_UNKNOWN",engine_identity)
  if not isinstance(authority_grants,list):return error(subject,as_of,"AUTHORITY_GRANT_MISSING",type(authority_grants).__name__)
  grants=[validate_grant(g,i) for i,g in enumerate(authority_grants)]
 except Exception as exc:return error(subject,as_of,"PROVIDER_EVIDENCE_MALFORMED",str(exc))

 out:list[Json]=[]
 if ev.get("kind")!="githubApprovalEvidence.v1":out.append(finding("PROVIDER_EVIDENCE_MALFORMED","githubApprovalEvidence.v1",ev.get("kind"),"ops","emit Accepted evidence schema"))
 if ev.get("provider")!="github":out.append(finding("PROVIDER_EVIDENCE_MALFORMED","github",ev.get("provider"),"ops","emit GitHub provider"))
 if ev.get("status")!="COMPLETE" or ev.get("findings")!=[]:out.append(finding("PROVIDER_EVIDENCE_MALFORMED","COMPLETE with no findings",{"status":ev.get("status"),"findings":ev.get("findings")},"ops","repair provider readback"))
 for key in ("repository_id","repository_full_name","pull_request_number","pull_request_id","candidate_revision","review_id","review_commit_id","review_state","review_submitted_at","review_dismissed","actor_account_id","actor_login","actor_type","observed_at","provider_response_digest","adapter_manifest_digest"):
  if ev.get(key) in (None,""):out.append(finding("PROVIDER_EVIDENCE_MALFORMED",f"non-empty {key}",ev.get(key),"ops","emit complete evidence"))
 if ev.get("repository_full_name")!=subject.get("repository"):out.append(finding("AUTHORITY_SCOPE_MISMATCH",subject.get("repository"),ev.get("repository_full_name"),"ops","read exact repository"))
 if ev.get("candidate_revision")!=subject.get("candidate_revision"):out.append(finding("CANDIDATE_REVISION_MISMATCH",subject.get("candidate_revision"),ev.get("candidate_revision"),"ops","bind exact revision"))
 if ev.get("review_commit_id")!=ev.get("candidate_revision"):out.append(finding("REVIEW_COMMIT_MISMATCH",ev.get("candidate_revision"),ev.get("review_commit_id"),"ops","read review commit"))
 if ev.get("review_state")!="APPROVED":out.append(finding("REVIEW_STATE_NOT_APPROVED","APPROVED",ev.get("review_state"),"ops","read approved review"))
 if ev.get("review_dismissed") is True:out.append(finding("REVIEW_DISMISSED",False,True,"ops","exclude dismissed review"))
 provider_evidence_digest=digest(ev)
 try:
  action_dt=when(ev.get("review_submitted_at"),"review_submitted_at")
  when(ev.get("observed_at"),"observed_at")
 except Exception as exc:
  out.append(finding("PROVIDER_EVIDENCE_MALFORMED","timezone-aware timestamps",str(exc),"ops","emit exact timestamps"));action_dt=None

 matches=[g for g in grants if (g.get("resource_scope") or {}).get("repository")==subject.get("repository")]
 if not matches:out.append(finding("AUTHORITY_GRANT_MISSING","one repository-scoped grant",0,"adrs","accept matching grant"))
 elif len(matches)>1:out.append(finding("AUTHORITY_GRANT_DUPLICATE","one repository-scoped grant",len(matches),"adrs","remove ambiguity"))
 grant=matches[0] if len(matches)==1 else None
 if grant:
  if grant.get("status")!="active":out.append(finding("AUTHORITY_GRANT_INACTIVE","active",grant.get("status"),"adrs","use active accepted grant"))
  binding=grant["provider_bindings"][0]
  if binding.get("provider")!="github":out.append(finding("ACTOR_BINDING_MISSING","github binding",binding,"adrs","accept GitHub numeric binding"))
  if binding.get("provider_account_id")!=ev.get("actor_account_id"):out.append(finding("ACTOR_PROVIDER_ID_MISMATCH",binding.get("provider_account_id"),ev.get("actor_account_id"),"adrs","bind numeric id"))
  if binding.get("provider_login")!=ev.get("actor_login"):out.append(finding("ACTOR_LOGIN_MISMATCH",binding.get("provider_login"),ev.get("actor_login"),"ops","read login for numeric id"))
  if "pull_request_review.approve" not in grant.get("action_kinds",[]):out.append(finding("ACTION_KIND_NOT_GRANTED",grant.get("action_kinds"),"pull_request_review.approve","adrs","grant exact action"))
  scope=grant["resource_scope"]
  expected_ids=scope["provider_object_ids"]
  actual_ids={"repository_id":ev.get("repository_id"),"pull_request_number":ev.get("pull_request_number"),"pull_request_id":ev.get("pull_request_id")}
  if actual_ids!=expected_ids:out.append(finding("PROVIDER_OBJECT_ID_MISMATCH",expected_ids,actual_ids,"ops","read exact object ids"))
  for key,actual,code,owner,next_action in (("repository",subject.get("repository"),"AUTHORITY_SCOPE_MISMATCH","adrs","use closed repository scope"),("candidate_revision",subject.get("candidate_revision"),"CANDIDATE_REVISION_MISMATCH","adrs","grant exact revision"),("finding_digest",subject.get("finding_digest"),"SUBJECT_DIGEST_MISMATCH","diagrams","bind exact finding"),("policy_digest",subject.get("policy_digest"),"POLICY_DIGEST_MISMATCH","diagrams","bind exact policy"),("subject_kind","diagram.waiver","AUTHORITY_SCOPE_MISMATCH","adrs","grant diagram waiver subject")):
   if scope.get(key)!=actual:out.append(finding(code,scope.get(key),actual,owner,next_action))
  if action_dt is not None:
   try:
    start,end=when(grant.get("valid_from"),"valid_from"),when(grant.get("valid_until"),"valid_until")
    if action_dt<start:out.append(finding("ACTION_TIME_OUTSIDE_GRANT",f">={grant.get('valid_from')}",ev.get("review_submitted_at"),"adrs","use evidence inside interval"))
    if action_dt>end:out.append(finding("AUTHORITY_GRANT_EXPIRED",f"<={grant.get('valid_until')}",ev.get("review_submitted_at"),"adrs","renew before approval"))
    if as_of_dt<action_dt:out.append(finding("ACTION_TIME_OUTSIDE_GRANT",f"<={as_of}",ev.get("review_submitted_at"),"ops","use as_of after action"))
   except Exception as exc:out.append(finding("AUTHORITY_GRANT_INACTIVE","valid interval",str(exc),"adrs","repair interval"))

 error_codes={"ACTOR_BINDING_MISSING","AUTHORITY_GRANT_MISSING","AUTHORITY_GRANT_DUPLICATE","PROVIDER_EVIDENCE_MALFORMED","AS_OF_MISSING","ENGINE_UNKNOWN","VALIDATION_EXCEPTION"}
 status=ERROR if {x["code"] for x in out}&error_codes else INVALID if out else VALID
 actor=action=authority=None;approval_id=None
 if grant and status==VALID:
  authority={"grant_id":grant["grant_id"],"scope_digest":digest(grant["resource_scope"]),"valid_from":grant["valid_from"],"valid_until":grant["valid_until"]}
  actor={"subject_id":grant["subject_id"],"provider":"github","provider_account_id":ev["actor_account_id"],"provider_login":ev["actor_login"]}
  action={"kind":"pull_request_review.approve","provider_review_id":ev["review_id"],"state":"APPROVED","submitted_at":ev["review_submitted_at"]}
  approval_id=digest({"grant_id":grant["grant_id"],**subject,"provider_evidence_digest":provider_evidence_digest,"engine_manifest_digest":engine_manifest_digest()})
 return {"kind":"approvalReceipt.v1","approval_id":approval_id,"subject":subject,"actor":actor,"action":action,"authority":authority,"provider_evidence_digest":provider_evidence_digest,"engine_manifest_digest":engine_manifest_digest(),"as_of":as_of,"status":status,"findings":sorted(out,key=lambda x:(x["code"],canonical(x))),"claim_ceiling":ceiling()}

def fixture()->tuple[list[Json],Json,Json,str,Json]:
 subject={"repository":"roccho-dev/diagrams","candidate_revision":"a"*40,"finding_digest":"sha256:"+"b"*64,"policy_digest":"sha256:"+"c"*64}
 grant={"kind":"authorityGrant.v1","grant_id":"G-001","subject_id":"person-or-role:diagram-approver","action_kinds":["pull_request_review.approve"],"resource_scope":{**subject,"subject_kind":"diagram.waiver","provider_object_ids":{"repository_id":1285891542,"pull_request_number":15,"pull_request_id":90000015}},"provider_bindings":[{"provider":"github","provider_account_id":40359643,"provider_login":"roccho-dev"}],"valid_from":"2026-07-01T00:00:00Z","valid_until":"2026-08-01T00:00:00Z","status":"active"}
 ev={"kind":"githubApprovalEvidence.v1","provider":"github","repository_id":1285891542,"repository_full_name":"roccho-dev/diagrams","pull_request_number":15,"pull_request_id":90000015,"candidate_revision":"a"*40,"review_id":7001,"review_commit_id":"a"*40,"review_state":"APPROVED","review_submitted_at":"2026-07-20T12:00:00Z","review_dismissed":False,"actor_account_id":40359643,"actor_login":"roccho-dev","actor_type":"User","observed_at":"2026-07-20T12:01:00Z","provider_response_digest":"sha256:"+"e"*64,"adapter_manifest_digest":"sha256:"+"f"*64,"status":"COMPLETE","findings":[],"claim_ceiling":{"authority_grant_validity_proven":False,**ceiling()}}
 engine={**engine_manifest(),"manifest_digest":engine_manifest_digest()}
 return [grant],ev,subject,"2026-07-20T12:02:00Z",engine

def selftest()->Json:
 grants,ev,subject,as_of,engine=fixture();valid=validate_approval(grants,ev,subject,as_of,engine)
 assert valid["status"]==VALID,valid
 assert canonical(valid)==canonical(validate_approval(grants,ev,subject,as_of,engine))
 assert valid["engine_manifest_digest"]==engine_manifest_digest()
 assert engine_manifest()["source_files"][0]["sha256"]==file_digest(source_path())
 assert engine_manifest_digest()!="sha256:"+hashlib.sha256(ENGINE_VERSION.encode()).hexdigest()
 mutations=[
 ("D01-numeric-id",lambda g,e,s,h:e.__setitem__("actor_account_id",1),"ACTOR_PROVIDER_ID_MISMATCH"),("D02-binding-absent",lambda g,e,s,h:g[0].__setitem__("provider_bindings",[]),"PROVIDER_EVIDENCE_MALFORMED"),("D03-revision",lambda g,e,s,h:s.__setitem__("candidate_revision","f"*40),"CANDIDATE_REVISION_MISMATCH"),("D04-state",lambda g,e,s,h:e.__setitem__("review_state","COMMENTED"),"REVIEW_STATE_NOT_APPROVED"),("D05-dismissed",lambda g,e,s,h:e.__setitem__("review_dismissed",True),"REVIEW_DISMISSED"),("D06-not-yet-valid",lambda g,e,s,h:g[0].__setitem__("valid_from","2026-07-21T00:00:00Z"),"ACTION_TIME_OUTSIDE_GRANT"),("D07-expired",lambda g,e,s,h:g[0].__setitem__("valid_until","2026-07-19T00:00:00Z"),"AUTHORITY_GRANT_EXPIRED"),("D08-revoked",lambda g,e,s,h:g[0].__setitem__("status","revoked"),"AUTHORITY_GRANT_INACTIVE"),("D09-repository",lambda g,e,s,h:s.__setitem__("repository","roccho-dev/ops"),"AUTHORITY_GRANT_MISSING"),("D10-action",lambda g,e,s,h:g[0].__setitem__("action_kinds",[]),"ACTION_KIND_NOT_GRANTED"),("D11-finding",lambda g,e,s,h:s.__setitem__("finding_digest","sha256:"+"0"*64),"SUBJECT_DIGEST_MISMATCH"),("D12-policy",lambda g,e,s,h:s.__setitem__("policy_digest","sha256:"+"0"*64),"POLICY_DIGEST_MISMATCH"),("D13-duplicate",lambda g,e,s,h:g.append(copy.deepcopy(g[0])),"AUTHORITY_GRANT_DUPLICATE"),("D14-evidence-status",lambda g,e,s,h:e.__setitem__("status","INCOMPLETE"),"PROVIDER_EVIDENCE_MALFORMED"),("D15-object-id",lambda g,e,s,h:e.__setitem__("pull_request_id",1),"PROVIDER_OBJECT_ID_MISMATCH"),("D16-current-permission",lambda g,e,s,h:e.__setitem__("current_permission","admin"),"PROVIDER_EVIDENCE_MALFORMED"),("D17-as-of",lambda g,e,s,h:h.__setitem__("as_of",None),"AS_OF_MISSING"),("D18-engine-version",lambda g,e,s,h:h["engine"].__setitem__("version","other"),"ENGINE_UNKNOWN"),("D19-engine-source",lambda g,e,s,h:h["engine"]["source_files"][0].__setitem__("sha256","sha256:"+"0"*64),"ENGINE_UNKNOWN"),("D20-intermediate-kind",lambda g,e,s,h:e.__setitem__("kind","providerApprovalEvidence.v1"),"PROVIDER_EVIDENCE_MALFORMED"),("D21-login",lambda g,e,s,h:e.__setitem__("actor_login","other"),"ACTOR_LOGIN_MISMATCH"),("D22-exception",lambda g,e,s,h:e.__setitem__("repository",{}),"PROVIDER_EVIDENCE_MALFORMED")]
 rejected=[]
 for name,mutate,expected in mutations:
  g,e,s,h=copy.deepcopy(grants),copy.deepcopy(ev),copy.deepcopy(subject),{"as_of":as_of,"engine":copy.deepcopy(engine)}
  mutate(g,e,s,h);receipt=validate_approval(g,e,s,h["as_of"],h["engine"]);codes={x["code"] for x in receipt["findings"]}
  assert expected in codes,(name,receipt);assert receipt["status"]!=VALID,(name,receipt);rejected.append(name)
 return {"kind":"approvalReceiptVerifier.selftest.v1","status":"PASS","positiveCases":1,"destructiveCases":len(rejected),"engineManifestDigest":engine_manifest_digest(),"schemaDigests":SCHEMA_DIGESTS,"cases":rejected,"claim_ceiling":ceiling()}

def main()->int:
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest="command",required=True);sub.add_parser("selftest");sub.add_parser("manifest");args=p.parse_args()
 value=selftest() if args.command=="selftest" else {**engine_manifest(),"manifest_digest":engine_manifest_digest()}
 print(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")));return 0
if __name__=="__main__":raise SystemExit(main())
