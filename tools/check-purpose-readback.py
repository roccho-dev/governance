#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

REQ_G1 = ["report_id","selected_objective_id","claimed_stop_ok","evidence_refs","machine_gate_results","unresolved_conflicts","unknowns","residual_risks","semantic_correctness_claim","business_value_claim","top_objective_closure_claim","requested_gen0_judgment"]
REQ_G0 = ["readback_id","selected_objective_id","gen1_report_ref","machine_gate_refs","judgment","why_sufficient_or_not","residual_risks","next_action"]
G1_JUDGMENTS = {"accept","continue","split","dispatch","reject","block"}
G0_JUDGMENTS = {"accept_selected_objective","continue_same_scope","split_scope","dispatch_review","reject_claim","block_on_policy_gap","escalate_objective_ambiguity"}
CLAIMS = {"none","authority_claimed","blocked_unknown"}
BIZ = {"none","separate_claim","blocked_unknown"}
TOP = {"none","indirect","separate_claim","blocked_unknown"}

def load(p):
    x = json.loads(Path(p).read_text(encoding="utf-8"))
    if not isinstance(x, dict):
        raise SystemExit(f"{p}: object required")
    return x

def rows(x): return isinstance(x, list) and len(x) > 0
def arr(x): return isinstance(x, list)
def txt(x): return isinstance(x, str) and bool(x.strip())

def add_missing(out, obj, fields, where):
    for f in fields:
        if f not in obj:
            out.append({"code":"missing-field","where":where,"field":f})

def bad_enum(out, obj, field, vals, where):
    if field in obj and obj[field] not in vals:
        out.append({"code":"bad-enum","where":where,"field":field})

def check(g1, g0=None):
    out = []
    add_missing(out, g1, REQ_G1, "gen1")
    if not txt(g1.get("selected_objective_id")):
        out.append({"code":"missing-selected-objective","where":"gen1"})
    if "approved" in g1 or "approval" in g1:
        out.append({"code":"self-approval","where":"gen1"})
    if g1.get("claimed_stop_ok") is True:
        if not rows(g1.get("evidence_refs")):
            out.append({"code":"stop-ok-without-evidence","where":"gen1"})
        if not rows(g1.get("machine_gate_results")):
            out.append({"code":"stop-ok-without-gate","where":"gen1"})
    for f in ["evidence_refs","machine_gate_results","unresolved_conflicts","unknowns","residual_risks"]:
        if f in g1 and not arr(g1[f]):
            out.append({"code":"bad-array","where":"gen1","field":f})
    bad_enum(out, g1, "requested_gen0_judgment", G1_JUDGMENTS, "gen1")
    bad_enum(out, g1, "semantic_correctness_claim", CLAIMS, "gen1")
    bad_enum(out, g1, "business_value_claim", BIZ, "gen1")
    bad_enum(out, g1, "top_objective_closure_claim", TOP, "gen1")
    if isinstance(g1.get("semantic_correctness_claim"), bool) or isinstance(g1.get("business_value_claim"), bool):
        out.append({"code":"boolean-claim","where":"gen1"})
    if str(g1.get("top_objective_closure_claim","")).lower() in {"closed","true","global_closed"}:
        out.append({"code":"global-closure-claim","where":"gen1"})
    if g1.get("business_value_claim") == "separate_claim":
        refs = g1.get("business_value_evidence_refs", g1.get("evidence_refs"))
        if rows(refs) and all(any(t in json.dumps(r).lower() for t in ["ci","pr","merge"]) for r in refs):
            out.append({"code":"ci-pr-merge-as-business-proof","where":"gen1"})
    if g1.get("requested_gen0_judgment") == "accept" and g0 is None:
        out.append({"code":"missing-gen0-readback-for-accept","where":"gen1"})
    if g0 is not None:
        add_missing(out, g0, REQ_G0, "gen0")
        if g0.get("selected_objective_id") != g1.get("selected_objective_id"):
            out.append({"code":"selected-objective-mismatch","where":"gen0"})
        bad_enum(out, g0, "judgment", G0_JUDGMENTS, "gen0")
        if g0.get("judgment") == "accept_selected_objective":
            if not rows(g0.get("machine_gate_refs")):
                out.append({"code":"accept-without-gate","where":"gen0"})
            if rows(g1.get("unresolved_conflicts")) and not rows(g0.get("residual_risks")):
                out.append({"code":"silent-conflict-resolution","where":"gen0"})
    return {"kind":"governance.purposeReadbackGate.report.v1","status":"fail" if out else "pass","findings":out}

def base_g1():
    return {"report_id":"g1","selected_objective_id":"obj","claimed_stop_ok":False,"evidence_refs":[],"machine_gate_results":[],"unresolved_conflicts":[],"unknowns":[],"residual_risks":[],"semantic_correctness_claim":"none","business_value_claim":"none","top_objective_closure_claim":"none","requested_gen0_judgment":"continue"}

def base_g0(j="continue_same_scope"):
    return {"readback_id":"g0","selected_objective_id":"obj","gen1_report_ref":"g1","machine_gate_refs":["gate"],"judgment":j,"why_sufficient_or_not":"bounded","residual_risks":[],"next_action":"continue"}

def expect(g1, g0, want):
    got = check(g1, g0)
    if (got["status"] == "pass") != want:
        raise SystemExit(json.dumps(got, indent=2, sort_keys=True))

def selftest():
    expect(base_g1(), None, True)
    expect(dict(base_g1(), requested_gen0_judgment="dispatch"), None, True)
    g1 = dict(base_g1(), claimed_stop_ok=True, evidence_refs=["adr"], machine_gate_results=["gate"], unresolved_conflicts=["risk"], requested_gen0_judgment="accept")
    expect(g1, dict(base_g0("accept_selected_objective"), residual_risks=["risk"]), True)
    x = dict(base_g1()); del x["selected_objective_id"]; expect(x, None, False)
    expect(dict(base_g1(), claimed_stop_ok=True, evidence_refs=["adr"], machine_gate_results=["gate"], requested_gen0_judgment="accept"), None, False)
    expect(dict(base_g1(), top_objective_closure_claim="closed"), None, False)
    x = dict(base_g1()); del x["unresolved_conflicts"]; expect(x, None, False)
    expect(dict(base_g1(), approval=True), None, False)
    expect(dict(base_g1(), business_value_claim="separate_claim", business_value_evidence_refs=["ci pass","pr merged"]), None, False)
    expect(g1, dict(base_g0("accept_selected_objective"), residual_risks=[]), False)
    print(json.dumps({"status":"purpose-readback-gate-selftest-pass"}, sort_keys=True))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", nargs="?", choices=["check","selftest"], default="check")
    ap.add_argument("--gen1-readback")
    ap.add_argument("--gen0-readback")
    a = ap.parse_args()
    if a.command == "selftest":
        selftest(); return 0
    if not a.gen1_readback:
        ap.error("check requires --gen1-readback")
    report = check(load(a.gen1_readback), load(a.gen0_readback) if a.gen0_readback else None)
    print(json.dumps(report, sort_keys=True, separators=(",",":")))
    return 1 if report["status"] == "fail" else 0

if __name__ == "__main__":
    sys.exit(main())
