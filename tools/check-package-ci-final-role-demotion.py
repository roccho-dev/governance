#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CI_INTENT = ROOT / "ci.intent.v1.jsonl"
WORKFLOWS = ROOT / ".github/workflows"
GATE = ".github/workflows/gov-final-scope-purpose-join.yml"
CANARY = ".github/workflows/gov-canary.yml"
CHECK_NAME = "gov-final-scope-purpose-join / gate"
CANDIDATE_SHA_SOURCE = "github.event.pull_request.head.sha || github.sha"
CUTOVER_STATE = "accepted-final-topology-live-receipt-bound"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def check(path: Path = CI_INTENT) -> dict[str, Any]:
    rows = read_jsonl(path)
    by_path = {row.get("path"): row for row in rows}
    actual = {
        item.relative_to(ROOT).as_posix()
        for item in WORKFLOWS.iterdir()
        if item.is_file() and item.suffix in {".yml", ".yaml"}
    }
    findings: list[dict[str, Any]] = []
    expected = {GATE, CANARY}
    if actual != expected:
        findings.append({"code": "workflow-universe", "expected": sorted(expected), "actual": sorted(actual)})
    if set(by_path) != expected or len(rows) != 2:
        findings.append({"code": "intent-universe", "expected": sorted(expected), "actual": sorted(by_path)})

    gate = by_path.get(GATE, {})
    canary = by_path.get(CANARY, {})
    if gate.get("role") != "primary_nix_check":
        findings.append({"code": "gate-role", "actual": gate.get("role")})
    if gate.get("authority") is not False or gate.get("authority_class") != "merge-admission":
        findings.append({"code": "gate-authority-boundary"})
    if gate.get("required_check_name") != CHECK_NAME:
        findings.append({"code": "check-name", "actual": gate.get("required_check_name")})
    if gate.get("candidate_sha_source") != CANDIDATE_SHA_SOURCE:
        findings.append({"code": "candidate-sha-source"})
    if gate.get("cutover_state") != CUTOVER_STATE:
        findings.append({"code": "cutover-state", "expected": CUTOVER_STATE, "actual": gate.get("cutover_state")})
    if gate.get("accepted_decision_merge") != "a8fc9e8e04d53f1d783317059e4421c8dc724d01":
        findings.append({"code": "accepted-decision"})
    if canary.get("role") != "bootstrap_exception" or canary.get("authority_class") != "evidence-only" or canary.get("authority") is not False:
        findings.append({"code": "canary-boundary"})
    exception = canary.get("exception")
    required_exception = {"owner", "reason", "expiry", "return_condition", "blocking_residual"}
    if not isinstance(exception, dict) or any(not exception.get(key) for key in required_exception):
        findings.append({"code": "canary-exception"})
    if gate.get("all_repositories_enforced") is not False or canary.get("all_repositories_enforced") is not False:
        findings.append({"code": "all-repository-overclaim"})

    gate_text = (ROOT / GATE).read_text(encoding="utf-8") if (ROOT / GATE).is_file() else ""
    canary_text = (ROOT / CANARY).read_text(encoding="utf-8") if (ROOT / CANARY).is_file() else ""
    if "check-live-final-ci-consumers.py capture" not in gate_text:
        findings.append({"code": "gate-live-consumer-capture"})
    if "--live-consumers" not in gate_text:
        findings.append({"code": "gate-live-consumer-join"})
    if "check-live-final-ci-consumers.py capture" not in canary_text:
        findings.append({"code": "canary-live-consumer-capture"})
    if "check-live-final-ci-control-plane.py check" not in canary_text:
        findings.append({"code": "canary-control-plane-observation"})

    return {
        "kind": "governance.ciFinalRoleDemotion.report.v3",
        "status": "pass" if not findings else "fail",
        "authority": False,
        "authorityClass": "evidence-only",
        "acceptedDecisionMerge": "a8fc9e8e04d53f1d783317059e4421c8dc724d01",
        "finalCheckName": CHECK_NAME,
        "cutoverState": CUTOVER_STATE,
        "expectedWorkflowCount": 2,
        "actualWorkflowCount": len(actual),
        "findings": findings,
        "boundary": "Two provider surfaces remain. The gate requires live selected-consumer artifact-body evidence; the canary observes live consumer and control-plane drift. ADRS retains meaning authority and all-repository enforcement remains false.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=["check", "selftest"], default="check")
    parser.add_argument("--ci-intent", type=Path, default=CI_INTENT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check(args.ci_intent)
    if args.command == "selftest" and report["status"] != "pass":
        raise SystemExit(canonical(report))
    print(canonical(report) if args.json else f"ci-final-role-demotion:{report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
