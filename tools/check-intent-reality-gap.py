#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

GAP_KINDS = {
    "missing_actual_state",
    "actual_state_drift",
    "purpose_not_met",
    "intent_conflict",
    "evidence_gap",
    "cost_or_complexity_drift",
}
ACTION_KINDS = {"create", "update", "delete", "rollback", "observe", "split", "reject"}
CLOSURE_GRADES = {"closed", "reduced", "not_closed", "split", "unknown"}
CLOSURE_VALUES = {"true", "false", "partial", "unknown"}
CLAIMS = {"none", "authority_claimed", "blocked_unknown"}
BUSINESS_CLAIMS = {"none", "separate_claim", "blocked_unknown"}

GAP_REQUIRED = [
    "gapId",
    "selectedObjectiveId",
    "intentRefs",
    "realityRefs",
    "gapKind",
    "actualStateSummary",
    "desiredStateSummary",
    "ownerRef",
    "expectedCloseCondition",
    "unknowns",
    "unresolvedConflicts",
]
ACTION_REQUIRED = [
    "actionId",
    "gapId",
    "actionKind",
    "expectedDelta",
    "postActionEvidenceRequired",
    "stopReason",
]
CLOSURE_REQUIRED = [
    "closureId",
    "gapId",
    "actionRefs",
    "postActionEvidenceRefs",
    "closesTowardSelectedObjective",
    "closureGrade",
    "whyClosedOrNot",
    "semanticCorrectnessClaim",
    "businessValueClaim",
    "unknowns",
    "unresolvedConflicts",
    "residualRisks",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise SystemExit(f"{path}:{line_no}: row must be object")
        rows.append(row)
    return rows


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and len(value) > 0


def list_value(value: Any) -> bool:
    return isinstance(value, list)


def add_missing(findings: list[dict[str, Any]], obj: dict[str, Any], fields: list[str], where: str) -> None:
    for field in fields:
        if field not in obj:
            findings.append({"diagnostic": "missing-field", "where": where, "field": field})


def first_diagnostic(findings: list[dict[str, Any]]) -> str | None:
    return findings[0]["diagnostic"] if findings else None


def validate_gap(gap: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not isinstance(gap, dict):
        return [{"diagnostic": "missing-gap", "where": "gap"}]

    add_missing(findings, gap, GAP_REQUIRED, "gap")
    if not non_empty_string(gap.get("selectedObjectiveId")):
        findings.append({"diagnostic": "missing-selected-objective", "where": "gap"})
    if not non_empty_list(gap.get("intentRefs")):
        findings.append({"diagnostic": "missing-intent-ref", "where": "gap"})
    if not list_value(gap.get("realityRefs")):
        findings.append({"diagnostic": "missing-reality-ref", "where": "gap"})
    elif not gap.get("realityRefs"):
        findings.append({"diagnostic": "missing-reality-ref", "where": "gap"})
    if gap.get("gapKind") == "missing_actual_state" and "missing_actual_state" not in (gap.get("realityRefs") or []):
        findings.append({"diagnostic": "missing-actual-state-marker", "where": "gap"})
    if gap.get("gapKind") not in GAP_KINDS:
        findings.append({"diagnostic": "bad-gap-kind", "where": "gap"})
    if not non_empty_string(gap.get("ownerRef")):
        findings.append({"diagnostic": "missing-owner", "where": "gap"})
    if not non_empty_string(gap.get("expectedCloseCondition")):
        findings.append({"diagnostic": "missing-close-condition", "where": "gap"})
    for field in ("unknowns", "unresolvedConflicts"):
        if field in gap and not list_value(gap[field]):
            findings.append({"diagnostic": "bad-array", "where": "gap", "field": field})
    return findings


def validate_action(action: Any, gap: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if action is None:
        return findings
    if not isinstance(action, dict):
        return [{"diagnostic": "bad-action", "where": "action"}]
    if not isinstance(gap, dict):
        findings.append({"diagnostic": "action-without-gap", "where": "action"})
    add_missing(findings, action, ACTION_REQUIRED, "action")
    if action.get("actionKind") not in ACTION_KINDS:
        findings.append({"diagnostic": "bad-action-kind", "where": "action"})
    if isinstance(gap, dict) and action.get("gapId") != gap.get("gapId"):
        findings.append({"diagnostic": "action-gap-mismatch", "where": "action"})
    if action.get("actionKind") == "create" and isinstance(gap, dict) and gap.get("gapKind") != "missing_actual_state":
        findings.append({"diagnostic": "create-without-missing-actual-state", "where": "action"})
    if action.get("actionKind") in {"update", "rollback", "delete"} and isinstance(gap, dict) and gap.get("gapKind") == "missing_actual_state":
        findings.append({"diagnostic": "update-delete-rollback-without-actual-state", "where": "action"})
    if "postActionEvidenceRequired" in action and not non_empty_list(action.get("postActionEvidenceRequired")):
        findings.append({"diagnostic": "missing-post-action-evidence-requirement", "where": "action"})
    return findings


def looks_like_ci_or_merge_only(refs: list[Any]) -> bool:
    if not refs:
        return False
    tokens = ("ci", "pr", "merge", "github-check")
    return all(any(token in str(ref).lower() for token in tokens) for ref in refs)


def validate_closure(closure: Any, gap: Any, action: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if closure is None:
        return findings
    if not isinstance(closure, dict):
        return [{"diagnostic": "bad-closure", "where": "closure"}]
    add_missing(findings, closure, CLOSURE_REQUIRED, "closure")
    if not isinstance(gap, dict):
        findings.append({"diagnostic": "closure-without-gap", "where": "closure"})
    elif closure.get("gapId") != gap.get("gapId"):
        findings.append({"diagnostic": "closure-gap-mismatch", "where": "closure"})
    if action is None:
        findings.append({"diagnostic": "closure-without-action", "where": "closure"})
    if closure.get("closureGrade") not in CLOSURE_GRADES:
        findings.append({"diagnostic": "bad-closure-grade", "where": "closure"})
    if closure.get("closesTowardSelectedObjective") not in CLOSURE_VALUES:
        findings.append({"diagnostic": "bad-closure-value", "where": "closure"})
    refs = closure.get("postActionEvidenceRefs")
    if not non_empty_list(refs):
        if closure.get("closureGrade") in {"closed", "reduced"} or closure.get("closesTowardSelectedObjective") in {"true", "partial"}:
            findings.append({"diagnostic": "closure-without-post-action-receipt", "where": "closure"})
    elif looks_like_ci_or_merge_only(refs):
        findings.append({"diagnostic": "ci-pr-merge-only-closure", "where": "closure"})
    if closure.get("semanticCorrectnessClaim") not in CLAIMS:
        findings.append({"diagnostic": "bad-semantic-claim", "where": "closure"})
    if closure.get("businessValueClaim") not in BUSINESS_CLAIMS:
        findings.append({"diagnostic": "bad-business-claim", "where": "closure"})
    for field in ("unknowns", "unresolvedConflicts", "residualRisks"):
        if field in closure and not list_value(closure[field]):
            findings.append({"diagnostic": "bad-array", "where": "closure", "field": field})
    return findings


def evaluate(row: dict[str, Any]) -> dict[str, Any]:
    gap = row.get("gap")
    action = row.get("action")
    closure = row.get("closure")
    findings = []
    findings.extend(validate_gap(gap))
    findings.extend(validate_action(action, gap))
    findings.extend(validate_closure(closure, gap, action))
    diagnostic = first_diagnostic(findings)
    return {
        "case": row.get("case"),
        "status": "fail" if findings else "pass",
        "diagnostic": diagnostic,
        "findings": findings,
    }


def check(rows: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for row in rows:
        result = evaluate(row)
        if row.get("expected") == "pass" and result["status"] != "pass":
            findings.append({"case": row.get("case"), "diagnostic": "unexpected-fail", "result": result})
        elif isinstance(row.get("expectedDiagnostic"), str):
            expected = row["expectedDiagnostic"]
            diagnostics = [item["diagnostic"] for item in result["findings"]]
            if expected not in diagnostics:
                findings.append({"case": row.get("case"), "diagnostic": "diagnostic-mismatch", "expected": expected, "result": result})
    return {
        "kind": "governance.intentRealityGapGate.report.v1",
        "status": "fail" if findings else "pass",
        "caseCount": len(rows),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args(argv)
    report = check(read_jsonl(args.fixtures))
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
