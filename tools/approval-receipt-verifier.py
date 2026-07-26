#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE_VERSION="approval-receipt-verifier.v1"
ENGINE_DIGEST="sha256:"+hashlib.sha256(ENGINE_VERSION.encode()).hexdigest()
VALID,INVALID,ERROR="VALID","INVALID","ERROR"
CODES={
"ACTOR_BINDING_MISSING","ACTOR_PROVIDER_ID_MISMATCH","ACTOR_LOGIN_MISMATCH",
"AUTHORITY_GRANT_MISSING","AUTHORITY_GRANT_DUPLICATE","AUTHORITY_GRANT_INACTIVE",
"AUTHORITY_GRANT_EXPIRED","AUTHORITY_SCOPE_MISMATCH","ACTION_KIND_NOT_GRANTED",
"CANDIDATE_REVISION_MISMATCH","REVIEW_COMMIT_MISMATCH","SUBJECT_DIGEST_MISMATCH",
"POLICY_DIGEST_MISMATCH","REVIEW_STATE_NOT_APPROVED","REVIEW_DISMISSED",
"PROVIDER_EVIDENCE_MALFORMED","PROVIDER_EVIDENCE_DIGEST_MISMATCH",
"PROVIDER_OBJECT_ID_MISMATCH","ACTION_TIME_OUTSIDE_GRANT","AS_OF_MISSING",
"ENGINE_UNKNOWN","VALIDATION_EXCEPTION"}
GRANT_KEYS={"kind","grant_id","subject_id","action_kinds","resource_scope","provider_bindings","valid_from","valid_until","status","grant_digest","accepted_decision_id","accepted_release_digest"}
EVIDENCE_KEYS={"kind","provider","provider_object_ids","repository_identity","candidate_revision","review_commit","action_kind","action_state","action_time","review_dismissed","actor_provider_account_id","actor_provider_login","observed_at","provider_response_digest","provider_evidence_digest","evidence_schema"}
SUBJECT_KEYS={"repository","candidate_revision","finding_digest","policy_digest"}
ENGINE_KEYS={"engine_version","engine_digest","schema_digests"}
Json=dict[str,Any]

def canonical(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def digest(v:Any)->str:return "sha256:"+hashlib.sha256(canonical(v).encode()).hexdigest()
def when(v:str,name:str)->datetime:
    if not isinstance(v,str) or not v:raise ValueError(f"{name}: required")
    d=datetime.fromisoformat(v.replace("Z","+00:00"))
    if d.tzinfo is None:raise ValueError(f"{name}: timezone required")
    return d.astimezone(timezone.utc)
def closed(v:Any,keys:set[str],name:str)->Json:
    if not isinstance(v,dict):raise ValueError(f"{name}: object required")
    unknown=set(v)-keys
    if unknown:raise ValueError(f"{name}: unknown keys {sorted(unknown)}")
    return v
def finding(code:str,expected:Any,actual:Any,owner:str,next_action:str)->Json:
    assert code in CODES
    return {"code":code,"expected":expected,"actual":actual,"owner":owner,"next_action":next_action}
def ceiling()->Json:
    return {"physical_human_identity_proven":False,"account_non_compromise_proven":False,"provider_independent_non_repudiation_proven":False}
def error(subject:Any,as_of:Any,code:str,actual:Any)->Json:
    return {"kind":"approvalReceipt.v1","approval_id":None,"subject":subject if isinstance(subject,dict) else None,"actor":None,"action":None,"authority":None,"provider_evidence_digest":None,"engine_digest":ENGINE_DIGEST,"as_of":as_of,"status":ERROR,"findings":[finding(code,"valid closed input",actual,"governance","repair input and rerun")],"claim_ceiling":ceiling()}

def validate_approval(authority_grants:list[Json],provider_evidence:Json,subject:Json,as_of:str|None,engine_identity:Json)->Json:
    """Pure provider-neutral evaluator: no I/O, network, environment, or implicit time."""
    try:
        if not as_of:return error(subject,as_of,"AS_OF_MISSING",as_of)
        as_of_dt=when(as_of,"as_of")
        subject=closed(subject,SUBJECT_KEYS,"subject")
        ev=closed(provider_evidence,EVIDENCE_KEYS,"provider_evidence")
        engine=closed(engine_identity,ENGINE_KEYS,"engine_identity")
        if engine.get("engine_version")!=ENGINE_VERSION or engine.get("engine_digest")!=ENGINE_DIGEST:
            return error(subject,as_of,"ENGINE_UNKNOWN",engine)
        schemas=engine.get("schema_digests")
        if not isinstance(schemas,dict) or not schemas or any(not isinstance(k,str) or not isinstance(v,str) or not v.startswith("sha256:") for k,v in schemas.items()):
            return error(subject,as_of,"ENGINE_UNKNOWN","schema_digests")
        if not isinstance(authority_grants,list):return error(subject,as_of,"AUTHORITY_GRANT_MISSING",type(authority_grants).__name__)
        grants=[closed(copy.deepcopy(g),GRANT_KEYS,f"authority_grants[{i}]") for i,g in enumerate(authority_grants)]
    except Exception as exc:return error(subject,as_of,"PROVIDER_EVIDENCE_MALFORMED",str(exc))

    out:list[Json]=[]
    if ev.get("kind")!="providerApprovalEvidence.v1":out.append(finding("PROVIDER_EVIDENCE_MALFORMED","providerApprovalEvidence.v1",ev.get("kind"),"ops","emit accepted envelope"))
    if ev.get("evidence_schema")!="githubApprovalEvidence.v1":out.append(finding("PROVIDER_EVIDENCE_MALFORMED","githubApprovalEvidence.v1",ev.get("evidence_schema"),"ops","emit accepted adapter schema"))
    if subject.get("repository")!=ev.get("repository_identity"):out.append(finding("AUTHORITY_SCOPE_MISMATCH",subject.get("repository"),ev.get("repository_identity"),"ops","read exact repository"))
    if subject.get("candidate_revision")!=ev.get("candidate_revision"):out.append(finding("CANDIDATE_REVISION_MISMATCH",subject.get("candidate_revision"),ev.get("candidate_revision"),"ops","bind exact revision"))
    if ev.get("review_commit")!=ev.get("candidate_revision"):out.append(finding("REVIEW_COMMIT_MISMATCH",ev.get("candidate_revision"),ev.get("review_commit"),"ops","read review commit"))
    if ev.get("action_state")!="APPROVED":out.append(finding("REVIEW_STATE_NOT_APPROVED","APPROVED",ev.get("action_state"),"ops","read approved review"))
    if ev.get("review_dismissed") is True:out.append(finding("REVIEW_DISMISSED",False,True,"ops","exclude dismissed review"))
    for k in ("provider_object_ids","actor_provider_account_id","actor_provider_login","provider_response_digest","provider_evidence_digest"):
        if ev.get(k) in (None,"",{},[]):out.append(finding("PROVIDER_EVIDENCE_MALFORMED",f"non-empty {k}",ev.get(k),"ops","emit complete evidence"))
    ids=ev.get("provider_object_ids")
    if ids is not None and not isinstance(ids,dict):out.append(finding("PROVIDER_EVIDENCE_MALFORMED","provider_object_ids object",ids,"ops","emit object identifiers"))
    calculated=digest({k:v for k,v in ev.items() if k!="provider_evidence_digest"})
    if ev.get("provider_evidence_digest")!=calculated:out.append(finding("PROVIDER_EVIDENCE_DIGEST_MISMATCH",calculated,ev.get("provider_evidence_digest"),"ops","recompute envelope digest"))
    try:action_dt=when(ev.get("action_time"),"action_time");when(ev.get("observed_at"),"observed_at")
    except Exception as exc:out.append(finding("PROVIDER_EVIDENCE_MALFORMED","timezone-aware timestamps",str(exc),"ops","emit exact timestamps"));action_dt=None

    matches=[g for g in grants if (g.get("resource_scope") or {}).get("repository")==subject.get("repository")]
    if not matches:out.append(finding("AUTHORITY_GRANT_MISSING","one repository-scoped grant",0,"adrs","accept matching grant"))
    elif len(matches)>1:out.append(finding("AUTHORITY_GRANT_DUPLICATE","one repository-scoped grant",len(matches),"adrs","remove ambiguity"))
    grant=matches[0] if len(matches)==1 else None
    if grant:
        if grant.get("status")!="Accepted":out.append(finding("AUTHORITY_GRANT_INACTIVE","Accepted",grant.get("status"),"adrs","use active accepted grant"))
        bindings=grant.get("provider_bindings") or []
        exact=[b for b in bindings if isinstance(b,dict) and b.get("provider")==ev.get("provider") and b.get("provider_account_id")==ev.get("actor_provider_account_id")]
        if not bindings:out.append(finding("ACTOR_BINDING_MISSING","accepted provider binding",bindings,"adrs","accept numeric binding"))
        elif not exact:out.append(finding("ACTOR_PROVIDER_ID_MISMATCH","accepted numeric id",ev.get("actor_provider_account_id"),"adrs","bind numeric id"))
        elif exact[0].get("provider_login")!=ev.get("actor_provider_login"):out.append(finding("ACTOR_LOGIN_MISMATCH",exact[0].get("provider_login"),ev.get("actor_provider_login"),"ops","read login for numeric id"))
        if ev.get("action_kind") not in (grant.get("action_kinds") or []):out.append(finding("ACTION_KIND_NOT_GRANTED",grant.get("action_kinds"),ev.get("action_kind"),"adrs","grant exact action"))
        scope=grant.get("resource_scope") or {}
        scoped_ids=scope.get("provider_object_ids")
        if scoped_ids is not None and (not isinstance(ids,dict) or any(ids.get(k)!=v for k,v in scoped_ids.items())):out.append(finding("PROVIDER_OBJECT_ID_MISMATCH",scoped_ids,ids,"ops","read exact object ids"))
        for key,code,owner,next_action in (
            ("repository","AUTHORITY_SCOPE_MISMATCH","adrs","use closed repository scope"),
            ("candidate_revision","CANDIDATE_REVISION_MISMATCH","adrs","grant exact revision"),
            ("finding_digest","SUBJECT_DIGEST_MISMATCH","diagrams","bind exact finding"),
            ("policy_digest","POLICY_DIGEST_MISMATCH","diagrams","bind exact policy")):
            if scope.get(key)!=subject.get(key):out.append(finding(code,scope.get(key),subject.get(key),owner,next_action))
        expected_grant=digest({k:v for k,v in grant.items() if k!="grant_digest"})
        if grant.get("grant_digest")!=expected_grant:out.append(finding("AUTHORITY_GRANT_INACTIVE",expected_grant,grant.get("grant_digest"),"adrs","rebuild grant digest"))
        if action_dt is not None:
            try:
                start,end=when(grant.get("valid_from"),"valid_from"),when(grant.get("valid_until"),"valid_until")
                if action_dt<start:out.append(finding("ACTION_TIME_OUTSIDE_GRANT",f">={grant.get('valid_from')}",ev.get("action_time"),"adrs","use evidence inside interval"))
                if action_dt>end:out.append(finding("AUTHORITY_GRANT_EXPIRED",f"<={grant.get('valid_until')}",ev.get("action_time"),"adrs","renew before approval"))
                if as_of_dt<action_dt:out.append(finding("ACTION_TIME_OUTSIDE_GRANT",f"<={as_of}",ev.get("action_time"),"ops","use as_of after action"))
            except Exception as exc:out.append(finding("AUTHORITY_GRANT_INACTIVE","valid interval",str(exc),"adrs","repair interval"))

    error_codes={"ACTOR_BINDING_MISSING","AUTHORITY_GRANT_MISSING","AUTHORITY_GRANT_DUPLICATE","PROVIDER_EVIDENCE_MALFORMED","AS_OF_MISSING","ENGINE_UNKNOWN","VALIDATION_EXCEPTION"}
    status=ERROR if {x["code"] for x in out}&error_codes else INVALID if out else VALID
    actor=action=authority=None;approval_id=None
    if grant and status==VALID:
        authority={"grant_id":grant["grant_id"],"scope_digest":digest(grant["resource_scope"]),"valid_from":grant["valid_from"],"valid_until":grant["valid_until"]}
        actor={"subject_id":grant["subject_id"],"provider":ev["provider"],"provider_account_id":ev["actor_provider_account_id"],"provider_login":ev["actor_provider_login"]}
        action={"kind":ev["action_kind"],"provider_review_id":ev["provider_object_ids"].get("review_id"),"state":ev["action_state"],"submitted_at":ev["action_time"]}
        approval_id=digest({"grant_id":grant["grant_id"],**subject,"provider_evidence_digest":ev["provider_evidence_digest"]})
    return {"kind":"approvalReceipt.v1","approval_id":approval_id,"subject":subject,"actor":actor,"action":action,"authority":authority,"provider_evidence_digest":ev.get("provider_evidence_digest"),"engine_digest":ENGINE_DIGEST,"as_of":as_of,"status":status,"findings":sorted(out,key=lambda x:(x["code"],canonical(x))),"claim_ceiling":ceiling()}

def fixture()->tuple[list[Json],Json,Json,str,Json]:
    subject={"repository":"roccho-dev/diagrams","candidate_revision":"a"*40,"finding_digest":"sha256:"+"b"*64,"policy_digest":"sha256:"+"c"*64}
    grant={"kind":"authorityGrant.v1","grant_id":"G-001","subject_id":"person-or-role:diagram-approver","action_kinds":["pull_request_review.approve"],"resource_scope":{**subject,"provider_object_ids":{"pull_request_number":15}},"provider_bindings":[{"provider":"github","provider_account_id":40359643,"provider_login":"roccho-dev"}],"valid_from":"2026-07-01T00:00:00Z","valid_until":"2026-08-01T00:00:00Z","status":"Accepted","grant_digest":"","accepted_decision_id":"01KYEW52E1KH8A709S1VPFK4PW","accepted_release_digest":"sha256:"+"d"*64}
    grant["grant_digest"]=digest({k:v for k,v in grant.items() if k!="grant_digest"})
    ev={"kind":"providerApprovalEvidence.v1","provider":"github","provider_object_ids":{"pull_request_number":15,"review_id":9001},"repository_identity":"roccho-dev/diagrams","candidate_revision":"a"*40,"review_commit":"a"*40,"action_kind":"pull_request_review.approve","action_state":"APPROVED","action_time":"2026-07-20T12:00:00Z","review_dismissed":False,"actor_provider_account_id":40359643,"actor_provider_login":"roccho-dev","observed_at":"2026-07-20T12:01:00Z","provider_response_digest":"sha256:"+"e"*64,"provider_evidence_digest":"","evidence_schema":"githubApprovalEvidence.v1"}
    ev["provider_evidence_digest"]=digest({k:v for k,v in ev.items() if k!="provider_evidence_digest"})
    engine={"engine_version":ENGINE_VERSION,"engine_digest":ENGINE_DIGEST,"schema_digests":{"authority":"sha256:"+"1"*64,"evidence":"sha256:"+"2"*64,"receipt":"sha256:"+"3"*64}}
    return [grant],ev,subject,"2026-07-20T12:02:00Z",engine

def selftest()->Json:
    grants,ev,subject,as_of,engine=fixture()
    valid=validate_approval(grants,ev,subject,as_of,engine)
    assert valid["status"]==VALID,valid
    assert canonical(valid)==canonical(validate_approval(grants,ev,subject,as_of,engine))
    mutations=[
    ("D01-numeric-id",lambda g,e,s,h:e.__setitem__("actor_provider_account_id",1),"ACTOR_PROVIDER_ID_MISMATCH"),
    ("D02-binding-absent",lambda g,e,s,h:g[0].__setitem__("provider_bindings",[]),"ACTOR_BINDING_MISSING"),
    ("D03-revision",lambda g,e,s,h:s.__setitem__("candidate_revision","f"*40),"CANDIDATE_REVISION_MISMATCH"),
    ("D04-state",lambda g,e,s,h:e.__setitem__("action_state","COMMENTED"),"REVIEW_STATE_NOT_APPROVED"),
    ("D05-dismissed",lambda g,e,s,h:e.__setitem__("review_dismissed",True),"REVIEW_DISMISSED"),
    ("D06-not-yet-valid",lambda g,e,s,h:g[0].__setitem__("valid_from","2026-07-21T00:00:00Z"),"ACTION_TIME_OUTSIDE_GRANT"),
    ("D07-expired",lambda g,e,s,h:g[0].__setitem__("valid_until","2026-07-19T00:00:00Z"),"AUTHORITY_GRANT_EXPIRED"),
    ("D08-inactive",lambda g,e,s,h:g[0].__setitem__("status","Revoked"),"AUTHORITY_GRANT_INACTIVE"),
    ("D09-repo",lambda g,e,s,h:s.__setitem__("repository","roccho-dev/ops"),"AUTHORITY_SCOPE_MISMATCH"),
    ("D10-action",lambda g,e,s,h:e.__setitem__("action_kind","pull_request_review.comment"),"ACTION_KIND_NOT_GRANTED"),
    ("D11-finding",lambda g,e,s,h:s.__setitem__("finding_digest","sha256:"+"9"*64),"SUBJECT_DIGEST_MISMATCH"),
    ("D12-policy",lambda g,e,s,h:s.__setitem__("policy_digest","sha256:"+"9"*64),"POLICY_DIGEST_MISMATCH"),
    ("D13-duplicate",lambda g,e,s,h:g.append(copy.deepcopy(g[0])),"AUTHORITY_GRANT_DUPLICATE"),
    ("D14-evidence-digest",lambda g,e,s,h:e.__setitem__("provider_evidence_digest","sha256:"+"0"*64),"PROVIDER_EVIDENCE_DIGEST_MISMATCH"),
    ("D15-object-id",lambda g,e,s,h:e.__setitem__("provider_object_ids",{"pull_request_number":16,"review_id":9001}),"PROVIDER_OBJECT_ID_MISMATCH"),
    ("D16-no-grant",lambda g,e,s,h:g.clear(),"AUTHORITY_GRANT_MISSING"),
    ("D17-as-of",lambda g,e,s,h:h.__setitem__("as_of",None),"AS_OF_MISSING"),
    ("D18-engine",lambda g,e,s,h:h["engine"].__setitem__("engine_digest","sha256:"+"0"*64),"ENGINE_UNKNOWN"),
    ("D19-provider-client",lambda g,e,s,h:e.__setitem__("github_client","x"),"PROVIDER_EVIDENCE_MALFORMED"),
    ("D20-ceiling",lambda g,e,s,h:None,None),
    ("D21-determinism",lambda g,e,s,h:None,None),
    ("D22-exception",lambda g,e,s,h:e.__setitem__("action_time","bad"),"PROVIDER_EVIDENCE_MALFORMED")]
    cases=[]
    for name,mut,expected in mutations:
        g,e,s,a,en=copy.deepcopy((grants,ev,subject,as_of,engine));holder={"as_of":a,"engine":en};mut(g,e,s,holder)
        result=validate_approval(g,e,s,holder["as_of"],holder["engine"])
        if name=="D20-ceiling":assert all(v is False for v in result["claim_ceiling"].values())
        elif name=="D21-determinism":assert canonical(result)==canonical(validate_approval(g,e,s,holder["as_of"],holder["engine"]))
        else:assert result["status"]!=VALID and expected in {x["code"] for x in result["findings"]},(name,result)
        cases.append({"case":name,"status":"PASS"})
    return {"kind":"approvalReceiptVerifier.selftest.v1","status":"PASS","positive":1,"destructive":cases,"engine_digest":ENGINE_DIGEST}

def main()->int:
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest="cmd",required=True);sub.add_parser("selftest")
    v=sub.add_parser("validate")
    for n in ("grants","evidence","subject","engine"):v.add_argument("--"+n,required=True)
    v.add_argument("--as-of",required=True);a=p.parse_args()
    if a.cmd=="selftest":print(json.dumps(selftest(),indent=2,sort_keys=True));return 0
    load=lambda n:json.loads(Path(getattr(a,n)).read_text())
    r=validate_approval(load("grants"),load("evidence"),load("subject"),a.as_of,load("engine"))
    print(json.dumps(r,ensure_ascii=False,indent=2,sort_keys=True));return 0 if r["status"]==VALID else 2 if r["status"]==INVALID else 3
if __name__=="__main__":raise SystemExit(main())
