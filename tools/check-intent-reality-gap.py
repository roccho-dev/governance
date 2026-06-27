#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any

GAP_KINDS = {"missing_actual_state","actual_state_drift","purpose_not_met","intent_conflict","evidence_gap","cost_or_complexity_drift"}
ACTION_KINDS = {"create","update","delete","rollback","observe","split","reject"}
CLOSURE_GRADES = {"closed","reduced","not_closed","split","unknown"}
CLOSURE_VALUES = {"true","false","partial","unknown"}
CLAIMS = {"none","authority_claimed","blocked_unknown"}
BIZ = {"none","separate_claim","blocked_unknown"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out=[]
    for n,line in enumerate(path.read_text(encoding="utf-8").splitlines(),1):
        if not line.strip():
            continue
        row=json.loads(line)
        if not isinstance(row,dict):
            raise SystemExit(f"{path}:{n}: row must be object")
        out.append(row)
    return out


def txt(x): return isinstance(x,str) and bool(x.strip())
def arr(x): return isinstance(x,list)
def rows(x): return isinstance(x,list) and bool(x)
def add(out, code, where, field=None):
    item={"diagnostic":code,"where":where}
    if field: item["field"]=field
    out.append(item)


def project(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    out=[]; p=row.get("purpose"); r=row.get("reality")
    if not isinstance(p,dict): add(out,"missing-purpose","purpose")
    if not isinstance(r,dict): add(out,"missing-reality","reality")
    if out: return None,out
    if not txt(p.get("selectedObjectiveId")): add(out,"missing-selected-objective","purpose")
    if not rows(p.get("intentRefs")): add(out,"missing-intent-ref","purpose")
    if not txt(p.get("desiredStateSummary")): add(out,"missing-desired-state","purpose")
    if not txt(p.get("ownerRef")): add(out,"missing-owner","purpose")
    if not txt(p.get("expectedCloseCondition")): add(out,"missing-close-condition","purpose")
    if not arr(r.get("realityRefs")) or not r.get("realityRefs"): add(out,"missing-reality-ref","reality")
    if r.get("realityState") not in GAP_KINDS: add(out,"bad-reality-state","reality")
    if r.get("realityState")=="missing_actual_state" and "missing_actual_state" not in (r.get("realityRefs") or []): add(out,"missing-actual-state-marker","reality")
    if not txt(r.get("actualStateSummary")): add(out,"missing-actual-state","reality")
    for where,obj in (("purpose",p),("reality",r)):
        for f in ("unknowns","unresolvedConflicts"):
            if f in obj and not arr(obj[f]): add(out,"bad-array",where,f)
    if out: return None,out
    return {"gapId":row.get("projectedGapId") or f"gap:{row.get('case','unknown')}","selectedObjectiveId":p["selectedObjectiveId"],"intentRefs":p["intentRefs"],"realityRefs":r["realityRefs"],"gapKind":r["realityState"],"actualStateSummary":r["actualStateSummary"],"desiredStateSummary":p["desiredStateSummary"],"ownerRef":p["ownerRef"],"expectedCloseCondition":p["expectedCloseCondition"],"unknowns":list(p.get("unknowns",[]))+list(r.get("unknowns",[])),"unresolvedConflicts":list(p.get("unresolvedConflicts",[]))+list(r.get("unresolvedConflicts",[]))},[]


def check_action(action: Any, gap: Any) -> list[dict[str, Any]]:
    out=[]
    if action is None: return out
    if not isinstance(action,dict): return [{"diagnostic":"bad-action","where":"action"}]
    if not isinstance(gap,dict): add(out,"action-without-gap","action")
    for f in ("actionId","gapId","actionKind","expectedDelta","postActionEvidenceRequired","stopReason"):
        if f not in action: add(out,"missing-field","action",f)
    if action.get("actionKind") not in ACTION_KINDS: add(out,"bad-action-kind","action")
    if isinstance(gap,dict) and action.get("gapId")!=gap.get("gapId"): add(out,"action-gap-mismatch","action")
    if action.get("actionKind")=="create" and isinstance(gap,dict) and gap.get("gapKind")!="missing_actual_state": add(out,"create-without-missing-actual-state","action")
    if action.get("actionKind") in {"update","rollback","delete"} and isinstance(gap,dict) and gap.get("gapKind")=="missing_actual_state": add(out,"update-delete-rollback-without-actual-state","action")
    if "postActionEvidenceRequired" in action and not rows(action.get("postActionEvidenceRequired")): add(out,"missing-post-action-evidence-requirement","action")
    return out


def ci_only(refs):
    toks=("ci","pr","merge","github-check")
    return rows(refs) and all(any(t in str(x).lower() for t in toks) for x in refs)


def check_closure(c: Any, gap: Any, action: Any) -> list[dict[str, Any]]:
    out=[]
    if c is None: return out
    if not isinstance(c,dict): return [{"diagnostic":"bad-closure","where":"closure"}]
    required=("closureId","gapId","actionRefs","postActionEvidenceRefs","closesTowardSelectedObjective","closureGrade","whyClosedOrNot","semanticCorrectnessClaim","businessValueClaim","unknowns","unresolvedConflicts","residualRisks")
    for f in required:
        if f not in c: add(out,"missing-field","closure",f)
    if not isinstance(gap,dict): add(out,"closure-without-gap","closure")
    elif c.get("gapId")!=gap.get("gapId"): add(out,"closure-gap-mismatch","closure")
    if action is None: add(out,"closure-without-action","closure")
    if c.get("closureGrade") not in CLOSURE_GRADES: add(out,"bad-closure-grade","closure")
    if c.get("closesTowardSelectedObjective") not in CLOSURE_VALUES: add(out,"bad-closure-value","closure")
    refs=c.get("postActionEvidenceRefs")
    if not rows(refs) and (c.get("closureGrade") in {"closed","reduced"} or c.get("closesTowardSelectedObjective") in {"true","partial"}): add(out,"closure-without-post-action-receipt","closure")
    elif ci_only(refs): add(out,"ci-pr-merge-only-closure","closure")
    if c.get("semanticCorrectnessClaim") not in CLAIMS: add(out,"bad-semantic-claim","closure")
    if c.get("businessValueClaim") not in BIZ: add(out,"bad-business-claim","closure")
    for f in ("unknowns","unresolvedConflicts","residualRisks"):
        if f in c and not arr(c[f]): add(out,"bad-array","closure",f)
    return out


def evaluate(row):
    gap,findings=project(row)
    findings += check_action(row.get("action"), gap)
    findings += check_closure(row.get("closure"), gap, row.get("action"))
    return {"case":row.get("case"),"status":"fail" if findings else "pass","diagnostic":findings[0]["diagnostic"] if findings else None,"projectedGap":gap,"findings":findings}


def check(rows_):
    findings=[]
    for row in rows_:
        got=evaluate(row)
        if row.get("expected")=="pass" and got["status"]!="pass": findings.append({"case":row.get("case"),"diagnostic":"unexpected-fail","result":got})
        elif isinstance(row.get("expectedDiagnostic"),str):
            diags=[x["diagnostic"] for x in got["findings"]]
            if row["expectedDiagnostic"] not in diags: findings.append({"case":row.get("case"),"diagnostic":"diagnostic-mismatch","expected":row["expectedDiagnostic"],"result":got})
    return {"kind":"governance.intentRealityProjectionGate.report.v1","status":"fail" if findings else "pass","caseCount":len(rows_),"findings":findings}


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--fixtures",type=Path,required=True); a=p.parse_args(argv)
    report=check(read_jsonl(a.fixtures)); print(json.dumps(report,sort_keys=True,separators=(",",":")))
    return 1 if report["status"]=="fail" else 0

if __name__=="__main__": sys.exit(main())
