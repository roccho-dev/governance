#!/usr/bin/env python3
"""Validate log-route join fixtures without provider access."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DIAGNOSTICS = {
    "missing-policy",
    "missing-receipt",
    "stale-receipt",
    "sink-drift",
    "policy-conflict",
    "authority-leak",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
        if not isinstance(row, dict):
            raise SystemExit(f"{path}:{line_no}: row must be object")
        rows.append(row)
    return rows


def match_selector(selector: Any, value: Any) -> bool:
    return selector in {"*", value}


def evaluate(row: dict[str, Any]) -> dict[str, Any]:
    case = row.get("case")
    policy = row.get("policy")
    deployment = row.get("deployment")
    receipt = row.get("receipt")
    if not isinstance(case, str) or not case:
        return {"case": case, "status": "fail", "diagnostic": "invalid-case"}
    if not isinstance(deployment, dict):
        return {"case": case, "status": "fail", "diagnostic": "missing-deployment"}
    if policy is None:
        return {"case": case, "status": "fail", "diagnostic": "missing-policy"}
    if not isinstance(policy, dict):
        return {"case": case, "status": "fail", "diagnostic": "policy-conflict"}
    if not match_selector(policy.get("serviceSelector"), deployment.get("serviceRef")):
        return {"case": case, "status": "fail", "diagnostic": "missing-policy"}
    if not match_selector(policy.get("environmentSelector"), deployment.get("environment")):
        return {"case": case, "status": "fail", "diagnostic": "missing-policy"}
    if not match_selector(policy.get("targetKindSelector"), deployment.get("targetKind")):
        return {"case": case, "status": "fail", "diagnostic": "missing-policy"}
    if not match_selector(policy.get("revisionSelector"), deployment.get("revisionRef")):
        return {"case": case, "status": "fail", "diagnostic": "policy-conflict"}
    if policy.get("blockingMode") == "conflict":
        return {"case": case, "status": "fail", "diagnostic": "policy-conflict"}
    if receipt is None:
        return {"case": case, "status": "fail", "diagnostic": "missing-receipt"}
    if not isinstance(receipt, dict):
        return {"case": case, "status": "fail", "diagnostic": "missing-receipt"}
    if receipt.get("authority") is True:
        return {"case": case, "status": "fail", "diagnostic": "authority-leak"}
    if receipt.get("revisionRef") != deployment.get("revisionRef"):
        return {"case": case, "status": "fail", "diagnostic": "stale-receipt"}
    if receipt.get("freshnessState") not in {"fresh", "current"}:
        return {"case": case, "status": "fail", "diagnostic": "stale-receipt"}
    if receipt.get("logSinkRef") != policy.get("logSinkRef"):
        return {"case": case, "status": "fail", "diagnostic": "sink-drift"}
    return {"case": case, "status": "pass", "diagnostic": None}


def check(rows: list[dict[str, Any]]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    seen_diagnostics: set[str] = set()
    for row in rows:
        result = evaluate(row)
        expected = row.get("expected")
        expected_diagnostic = row.get("expectedDiagnostic")
        diagnostic = result.get("diagnostic")
        if isinstance(diagnostic, str) and diagnostic in DIAGNOSTICS:
            seen_diagnostics.add(diagnostic)
        if expected == "pass":
            if result.get("status") != "pass":
                findings.append({"case": row.get("case"), "code": "unexpected-fail", "result": result})
        elif isinstance(expected_diagnostic, str):
            if diagnostic != expected_diagnostic:
                findings.append({"case": row.get("case"), "code": "diagnostic-mismatch", "expected": expected_diagnostic, "result": result})
        else:
            findings.append({"case": row.get("case"), "code": "missing-expectation"})
    missing_declared = {"missing-policy", "missing-receipt", "sink-drift", "authority-leak"} - seen_diagnostics
    if missing_declared:
        findings.append({"code": "missing-required-diagnostic-coverage", "diagnostics": sorted(missing_declared)})
    return {
        "kind": "governance.logRouteJoinFixture.report.v1",
        "status": "fail" if findings else "pass",
        "caseCount": len(rows),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    args = parser.parse_args(argv)
    report = check(read_jsonl(args.fixtures))
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
