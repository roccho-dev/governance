#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs" / "final-scope-purpose-join"
CASES = BASE / "merge-write-boundary-cases.jsonl"
PROOF = BASE / "merge-write-boundary-proof.json"
FINAL_CHECK_NAME = "gov-final-scope-purpose-join / gate"
SELECTED_REF = "refs/heads/proposals"
ALLOWED_ENFORCEMENT_POINTS = {
    "github-ruleset",
    "branch-protection",
    "server-side-hook",
    "merge-daemon",
    "bot-only-merge",
    "ssot-publish-gate",
}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(canonical({"status": "fail", "path": str(path), "line": line_no, "reason": str(exc)})) from exc
        if not isinstance(row, dict):
            raise SystemExit(canonical({"status": "fail", "path": str(path), "line": line_no, "reason": "row-not-object"}))
        rows.append(row)
    return rows


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(canonical({"status": "fail", "path": str(path), "reason": "json-not-object"}))
    return value


def finding(code: str, message: str, **extra: Any) -> dict[str, Any]:
    row = {"code": code, "message": message}
    row.update(extra)
    return row


def is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{40}", value))


def is_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(DIGEST_RE.fullmatch(value))


def decision_for_case(row: dict[str, Any]) -> dict[str, Any]:
    gate = row.get("finalGate") if isinstance(row.get("finalGate"), dict) else {}
    old_ci = row.get("oldCi") if isinstance(row.get("oldCi"), dict) else {}
    reasons: list[str] = []

    target_ref = row.get("targetRef")
    target_sha = row.get("targetSha")
    gate_name = gate.get("name")
    gate_status = gate.get("status")
    gate_target_sha = gate.get("targetSha")
    gate_output_digest = gate.get("outputDigest")
    enforcement_point = row.get("enforcementPoint")
    actor = row.get("actor")

    if row.get("kind") != "governance.mergeWriteBoundary.case.v1":
        reasons.append("case-kind-invalid")
    if target_ref != SELECTED_REF:
        reasons.append("target-ref-not-selected")
    if not is_sha(target_sha):
        reasons.append("target-sha-invalid")
    if enforcement_point not in ALLOWED_ENFORCEMENT_POINTS:
        reasons.append("enforcement-point-invalid")
    if actor == "human-direct":
        reasons.append("direct-human-write-rejected")
    if gate_name != FINAL_CHECK_NAME:
        reasons.append("final-gate-name-mismatch")
    if gate_status != "pass":
        reasons.append("final-gate-not-pass")
    if gate_target_sha != target_sha:
        reasons.append("target-sha-mismatch")
    if not is_digest(gate_output_digest):
        reasons.append("final-gate-digest-missing")
    if old_ci.get("status") == "success" and gate_status != "pass":
        reasons.append("old-ci-not-authority")

    decision = "allow" if not reasons else "reject"
    return {
        "kind": "governance.mergeWriteBoundary.auditReceipt.v1",
        "caseId": row.get("caseId"),
        "authority": False,
        "selectedRef": target_ref,
        "targetSha": target_sha,
        "decision": decision,
        "reasons": reasons,
        "finalGateName": gate_name,
        "finalGateStatus": gate_status,
        "finalGateTargetSha": gate_target_sha,
        "finalGateRunId": gate.get("runId"),
        "finalGateOutputDigest": gate_output_digest,
        "oldCiStatus": old_ci.get("status"),
        "actor": actor,
        "enforcementPoint": enforcement_point,
        "attemptedAt": row.get("attemptedAt"),
    }


def build_report(cases_path: Path = CASES) -> dict[str, Any]:
    cases = read_jsonl(cases_path)
    receipts = [decision_for_case(row) for row in cases]
    findings: list[dict[str, Any]] = []

    for row, receipt in zip(cases, receipts):
        expected = row.get("expectedDecision")
        if expected not in {"allow", "reject"}:
            findings.append(finding("expected-decision-invalid", "case must declare expectedDecision", caseId=row.get("caseId")))
            continue
        if receipt["decision"] != expected:
            findings.append(
                finding(
                    "decision-mismatch",
                    "merge/write boundary decision does not match expected fixture outcome",
                    caseId=row.get("caseId"),
                    expected=expected,
                    actual=receipt["decision"],
                    reasons=receipt["reasons"],
                )
            )
        for required in ["targetSha", "decision", "finalGateName", "finalGateRunId", "actor", "enforcementPoint", "attemptedAt"]:
            if receipt.get(required) in {None, ""}:
                findings.append(finding("audit-receipt-field-missing", "audit receipt is missing a required field", caseId=row.get("caseId"), field=required))

    decisions = {receipt["caseId"]: receipt["decision"] for receipt in receipts}
    if not any(receipt["decision"] == "allow" for receipt in receipts):
        findings.append(finding("accept-proof-missing", "at least one exact-SHA final-gate pass must be allowed"))
    if not any("final-gate-not-pass" in receipt["reasons"] for receipt in receipts):
        findings.append(finding("reject-proof-missing-final-gate", "must reject updates without final gate pass"))
    if not any("target-sha-mismatch" in receipt["reasons"] for receipt in receipts):
        findings.append(finding("reject-proof-missing-stale-target", "must reject stale or mismatched target SHA"))
    if not any("direct-human-write-rejected" in receipt["reasons"] for receipt in receipts):
        findings.append(finding("reject-proof-missing-direct-write", "must reject direct human writes in provider-neutral policy"))

    return {
        "kind": "governance.mergeWriteBoundaryFinalGate.proof.v1",
        "status": "pass" if not findings else "fail",
        "authority": False,
        "parent": "governance#125",
        "phaseIssue": "governance#115",
        "selectedRef": SELECTED_REF,
        "finalGateName": FINAL_CHECK_NAME,
        "providerNeutral": True,
        "allowedEnforcementPoints": sorted(ALLOWED_ENFORCEMENT_POINTS),
        "caseCount": len(cases),
        "allowCount": sum(1 for receipt in receipts if receipt["decision"] == "allow"),
        "rejectCount": sum(1 for receipt in receipts if receipt["decision"] == "reject"),
        "auditReceiptCount": len(receipts),
        "decisions": decisions,
        "receipts": receipts,
        "findings": findings,
        "boundary": "This proves the provider-neutral merge/write boundary decision rule and audit receipt format. It does not mutate GitHub rulesets, make governance meaning authority, or claim selected real package closure-pass by itself.",
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def selftest() -> dict[str, Any]:
    report = build_report()
    checked = read_json(PROOF)
    if checked != report:
        raise SystemExit(canonical({"status": "fail", "reason": "checked merge/write boundary proof does not match generated report", "expected": report, "actual": checked}))
    if report["status"] != "pass":
        raise SystemExit(canonical(report))
    return {
        "kind": "governance.mergeWriteBoundaryFinalGate.selftest.v1",
        "status": "pass",
        "authority": False,
        "phaseIssue": "governance#115",
        "finalGateName": FINAL_CHECK_NAME,
        "selectedRef": SELECTED_REF,
        "allowCount": report["allowCount"],
        "rejectCount": report["rejectCount"],
        "auditReceiptCount": report["auditReceiptCount"],
        "proofArtifact": PROOF.relative_to(ROOT).as_posix(),
        "boundary": report["boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate provider-neutral merge/write boundary final-gate decisions.")
    parser.add_argument("command", nargs="?", choices=["check", "build", "selftest"], default="check")
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.command == "selftest":
        report = selftest()
    else:
        report = build_report(args.cases)
        if args.command == "build" and args.out:
            write_report(args.out, report)
    print(canonical(report) if args.json else f"merge-write-boundary-final-gate:{report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
