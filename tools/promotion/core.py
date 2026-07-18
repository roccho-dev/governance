from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .ed25519 import verify as verify_ed25519

SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
ZERO_DIGEST = "sha256:" + "0" * 64
EVENT_FIELDS = {"kind","promotionId","subject","sequence","candidateDigest","acceptedDecisionDigest","gateDecisionDigest","claimSetDigest","receiptSetDigest","previousPromotionDigest","operation","publisherKeyId","signature","bootstrap"}

class PromotionError(ValueError): pass

def need(ok: bool, code: str) -> None:
    if not ok: raise PromotionError(code)

def canonical(value: Any) -> bytes:
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",", ":")).encode()

def digest(value: Any) -> str: return "sha256:"+hashlib.sha256(canonical(value)).hexdigest()
def key_id(public: bytes) -> str: return hashlib.sha256(public).hexdigest()
def unsigned_event(event: dict[str,Any]) -> dict[str,Any]: return {k:v for k,v in event.items() if k!="signature"}
def event_digest(event: dict[str,Any]) -> str: return digest(event)

@dataclass(frozen=True)
class Policy:
    contract_digest: str
    public_key: bytes|None
    public_key_id: str|None
    production_key_provisioned: bool
    accepted_decision_status: str
    max_bootstrap_count: int=1

    @staticmethod
    def from_dict(value: dict[str,Any]) -> "Policy":
        need(value.get("kind")=="governance.promotionPolicyShadow.v1","policy-kind")
        need(SHA256.fullmatch(str(value.get("contractDigest",""))) is not None,"policy-contract-digest")
        key=value.get("publisherKey",{}); provisioned=key.get("status")=="provisioned"; public_hex=key.get("publicKeyHex")
        public=bytes.fromhex(public_hex) if provisioned and isinstance(public_hex,str) else None; public_id=key.get("keyId") if provisioned else None
        if provisioned:
            need(public is not None and len(public)==32,"policy-public-key"); need(public_id==key_id(public),"policy-key-id")
        need(value.get("providerAuthority") is False,"policy-provider-authority"); need(value.get("githubMergeHasAuthority") is False,"policy-github-merge"); need(value.get("githubRulesetRequired") is False,"policy-ruleset"); need(value.get("allRepositoriesEnforced") is False,"policy-all-repositories"); need(value.get("businessOutcomeAchieved") is False,"policy-business-outcome")
        return Policy(value["contractDigest"],public,public_id,provisioned,value.get("acceptedDecisionStatus","proposed"),int(value.get("maximumBootstrapCount",1)))

def make_promotion_candidate(*,candidate_digest:str,accepted_decision_digest:str,gate_report:dict[str,Any],claim_set_digest:str,receipt_set_digest:str,engine_digest:str,accepted_decision_status:str)->dict[str,Any]:
    need(GIT_SHA.fullmatch(candidate_digest) is not None or SHA256.fullmatch(candidate_digest) is not None,"candidate-digest")
    for code,value in [("accepted-decision",accepted_decision_digest),("claim-set",claim_set_digest),("receipt-set",receipt_set_digest),("engine",engine_digest)]: need(SHA256.fullmatch(value) is not None,code)
    need(gate_report.get("status")=="pass" and gate_report.get("decision")=="allow","gate-not-allow"); need(gate_report.get("candidateSha")==candidate_digest,"gate-candidate-mismatch")
    admitted=accepted_decision_status=="accepted"
    result={"kind":"promotionCandidate.v1","status":"pass","candidateDigest":candidate_digest,"acceptedDecisionDigest":accepted_decision_digest,"acceptedDecisionStatus":accepted_decision_status,"gateDecisionDigest":digest(gate_report),"claimSetDigest":claim_set_digest,"receiptSetDigest":receipt_set_digest,"engineDigest":engine_digest,"decision":"allow" if admitted else "shadow-allow","promotionAdmission":admitted,"authority":False,"effectAuthority":False,"githubMergeHasAuthority":False,"githubRulesetRequired":False,"allRepositoriesEnforced":False,"businessOutcomeAchieved":False}
    result["packetDigest"]=digest(result); return result

def verify_event(event:dict[str,Any],policy:Policy)->None:
    need(set(event)==EVENT_FIELDS,"event-fields"); need(event["kind"]=="promotion.v1","event-kind"); need(isinstance(event["promotionId"],str) and event["promotionId"],"promotion-id"); need(isinstance(event["subject"],str) and event["subject"],"subject"); need(isinstance(event["sequence"],int) and event["sequence"]>=0,"sequence")
    need(GIT_SHA.fullmatch(str(event["candidateDigest"])) is not None or SHA256.fullmatch(str(event["candidateDigest"])) is not None,"event-candidate")
    for field in ["acceptedDecisionDigest","gateDecisionDigest","claimSetDigest","receiptSetDigest","previousPromotionDigest"]: need(SHA256.fullmatch(str(event[field])) is not None,f"event-{field}")
    need(event["operation"] in {"promote","rollback","revoke"},"operation"); need(isinstance(event["bootstrap"],bool),"bootstrap"); need(policy.production_key_provisioned and policy.public_key is not None,"production-key-unprovisioned"); need(event["publisherKeyId"]==policy.public_key_id,"publisher-key-id"); need(event["acceptedDecisionDigest"]==policy.contract_digest,"accepted-decision-digest")
    try: signature=bytes.fromhex(event["signature"])
    except ValueError as exc: raise PromotionError("signature-invalid") from exc
    need(verify_ed25519(policy.public_key,canonical(unsigned_event(event)),signature),"signature-invalid")

def order_chain(events:Iterable[dict[str,Any]],policy:Policy)->list[dict[str,Any]]:
    rows=[copy.deepcopy(row) for row in events]; need(rows,"chain-empty"); by_digest={}; next_by_previous={}; ids=set()
    for row in rows:
        verify_event(row,policy); d=event_digest(row); need(d not in by_digest,"duplicate-event"); need(row["promotionId"] not in ids,"duplicate-promotion-id"); ids.add(row["promotionId"]); by_digest[d]=row; next_by_previous.setdefault(row["previousPromotionDigest"],[]).append(row)
    genesis=next_by_previous.get(ZERO_DIGEST,[]); need(len(genesis)==1,"genesis-cardinality"); ordered=[]; current=genesis[0]; visited=set()
    while True:
        d=event_digest(current); need(d not in visited,"chain-cycle"); visited.add(d); ordered.append(current); children=next_by_previous.get(d,[]); need(len(children)<=1,"chain-fork")
        if not children: break
        current=children[0]
    need(len(ordered)==len(rows),"chain-disconnected"); sequences={}; bootstrap_count=0
    for index,row in enumerate(ordered):
        expected=sequences.get(row["subject"],0); need(row["sequence"]==expected,"subject-sequence"); sequences[row["subject"]]=expected+1
        if row["bootstrap"]:
            bootstrap_count+=1; need(row["subject"]=="repo:roccho-dev/governance","bootstrap-subject"); need(index==1,"bootstrap-position")
    need(bootstrap_count<=policy.max_bootstrap_count,"bootstrap-reuse"); return ordered

def reduce_selected(events:Iterable[dict[str,Any]],policy:Policy)->dict[str,Any]:
    ordered=order_chain(events,policy); selected={}; history={}
    for row in ordered:
        subject=row["subject"]
        if subject.startswith("system:"): continue
        candidate=row["candidateDigest"]; op=row["operation"]
        if op=="promote": history.setdefault(subject,[]).append(candidate); selected[subject]={"candidateDigest":candidate,"promotionId":row["promotionId"],"eventDigest":event_digest(row)}
        elif op=="rollback": need(candidate in history.get(subject,[]),"rollback-target-not-history"); selected[subject]={"candidateDigest":candidate,"promotionId":row["promotionId"],"eventDigest":event_digest(row)}
        else: need(subject in selected,"revoke-unselected"); selected.pop(subject)
    projection={"kind":"selectedPromotionProjection.v1","status":"pass","authority":False,"chainValid":True,"providerAuthority":False,"selected":selected,"eventCount":len(ordered),"chainHeadDigest":event_digest(ordered[-1]),"bootstrapConsumed":any(row["bootstrap"] for row in ordered),"allRepositoriesEnforced":False,"businessOutcomeAchieved":False}; projection["projectionDigest"]=digest(projection); return projection
