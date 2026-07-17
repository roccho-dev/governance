#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CI_INTENT = ROOT / "ci.intent.v1.jsonl"
WORKFLOWS = ROOT / ".github" / "workflows"
FINAL_CHECK_NAME = "gov-final-scope-purpose-join / gate"
FINAL_ROLE = "primary_required_surface_after_accepted_cutover"
CUTOVER_STATE = "pre-acceptance-current-sha-fixture"

EXPECTED_FINAL_ROLES = {
    ".github/workflows/gov-final-scope-purpose-join.yml": FINAL_ROLE,
    ".github/workflows/ci.yml": "receipt_producer_and_tool_selftest_after_cutover",
    ".github/workflows/manual-ci.yml": "manual_observation_only",
    ".github/workflows/adrs-shadow-monitor.yml": "artifact_or_shadow_observer",
    ".github/workflows/repo-explain-artifact-minimal.yml": "artifact_producer_not_merge_authority",
    ".github/workflows/repo-governance.yml": "tool_selftest_not_merge_authority",
    ".github/workflows/readme-artifact.yml": "artifact_producer_not_merge_authority",
    ".github/workflows/claim-port-join.yml": "final_join_internal_step_or_tool_selftest",
    ".github/workflows/claim-port-org-admission.yml": "final_join_admission_step",
    ".github/workflows/log-route-join.yml": "final_join_internal_step_or_tool_selftest",
    ".github/workflows/intent-reality-gap.yml": "final_join_internal_step_or_tool_selftest",
    ".github/workflows/adrs-code-governance-fixture.yml": "artifact_or_shadow_observer",
}
NON_AUTHORITY_FINAL_ROLES = set(EXPECTED_FINAL_ROLES.values()) - {FINAL_ROLE}
REQUIRED_EXCEPTION_FIELDS = {"owner", "reason", "expiry", "return_condition", "blocking_residual"}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
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


def workflow_files() -> set[str]:
    if not WORKFLOWS.exists():
        return set()
    return {
        path.relative_to(ROOT).as_posix()
        for path in WORKFLOWS.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    }


def finding(code: str, message: str, **extra: Any) -> dict[str, Any]:
    row = {"code": code, "message": message}
    row.update(extra)
    return row


def check(path: Path = CI_INTENT) -> dict[str, Any]:
    rows = read_jsonl(path)
    by_path = {row.get("path"): row for row in rows if isinstance(row.get("path"), str)}
    findings: list[dict[str, Any]] = []

    actual = workflow_files()
    expected = set(EXPECTED_FINAL_ROLES)
    for workflow_path in sorted(actual - set(by_path)):
        findings.append(finding("workflow-undemoted", "workflow exists without ci.intent row", path=workflow_path))
    for workflow_path in sorted(set(by_path) - actual):
        findings.append(finding("intent-without-workflow", "ci.intent row has no workflow", path=workflow_path))
    if actual != expected:
        findings.append(finding("workflow-universe-mismatch", "workflow universe differs from the bounded 12-surface inventory", expected=sorted(expected), actual=sorted(actual)))

    for workflow_path, expected_role in sorted(EXPECTED_FINAL_ROLES.items()):
        row = by_path.get(workflow_path)
        if row is None:
            findings.append(finding("final-role-row-missing", "expected workflow row is missing", path=workflow_path))
            continue
        if row.get("authority") is not False:
            findings.append(finding("workflow-authority-invalid", "workflow authority must remain false before accepted cutover", path=workflow_path))
        actual_role = row.get("final_role")
        if actual_role != expected_role:
            findings.append(finding("final-role-mismatch", "workflow final_role does not match the bounded migration plan", path=workflow_path, expected=expected_role, actual=actual_role))
        if expected_role in NON_AUTHORITY_FINAL_ROLES and row.get("required_check_name"):
            findings.append(finding("old-ci-required-check-name", "non-final CI surface must not declare a required final check name", path=workflow_path))

    gate = by_path.get(".github/workflows/gov-final-scope-purpose-join.yml", {})
    if gate.get("required_check_name") != FINAL_CHECK_NAME:
        findings.append(finding("final-check-name-mismatch", "final gate must preserve the exact check name", expected=FINAL_CHECK_NAME, actual=gate.get("required_check_name")))
    if gate.get("cutover_state") != CUTOVER_STATE:
        findings.append(finding("cutover-state-mismatch", "final gate must remain in the accepted pre-cutover fixture state", expected=CUTOVER_STATE, actual=gate.get("cutover_state")))
    if gate.get("authority_class") != "evidence-only":
        findings.append(finding("gate-authority-class-invalid", "pre-acceptance gate must be evidence-only", actual=gate.get("authority_class")))
    exception = gate.get("exception")
    if not isinstance(exception, dict):
        findings.append(finding("gate-exception-missing", "pre-acceptance gate requires a bounded exception contract"))
    else:
        missing = sorted(field for field in REQUIRED_EXCEPTION_FIELDS if not exception.get(field))
        if missing:
            findings.append(finding("gate-exception-incomplete", "pre-acceptance gate exception is incomplete", missing=missing))

    return {
        "kind": "governance.ciFinalRoleDemotion.report.v1",
        "status": "pass" if not findings else "fail",
        "authority": False,
        "authorityClass": "evidence-only",
        "finalCheckName": FINAL_CHECK_NAME,
        "cutoverState": CUTOVER_STATE,
        "checkedIntentPath": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
        "expectedWorkflowCount": len(EXPECTED_FINAL_ROLES),
        "actualWorkflowCount": len(actual),
        "findings": findings,
        "boundary": "This validates the bounded 12-surface inventory, non-authority demotion, stable check identity, and pre-acceptance fixture state. It performs no ruleset cutover, effect, or workflow deletion.",
    }


def selftest() -> dict[str, Any]:
    report = check()
    if report["status"] != "pass":
        raise SystemExit(canonical(report))
    return {
        "kind": "governance.ciFinalRoleDemotion.selftest.v1",
        "status": "pass",
        "authority": False,
        "authorityClass": "evidence-only",
        "finalCheckName": FINAL_CHECK_NAME,
        "coveredIssues": ["governance#117", "governance#118", "governance#150"],
        "report": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate final-role demotion for old CI surfaces.")
    parser.add_argument("command", nargs="?", choices=["check", "selftest"], default="check")
    parser.add_argument("--ci-intent", type=Path, default=CI_INTENT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = selftest() if args.command == "selftest" else check(args.ci_intent)
    print(canonical(report) if args.json else f"ci-final-role-demotion:{report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
