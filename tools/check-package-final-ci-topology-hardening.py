#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "tools/check-package-final-ci-topology.py"
INVENTORY = ROOT / "governance/ci-topology-150.jsonl"
PACKET = ROOT / "fixtures/final-ci-topology/governance-fixture.json"
GATE_PATH = ".github/workflows/gov-final-scope-purpose-join.yml"
EXPECTED_REPOSITORY = "roccho-dev/governance"
EXPECTED_DECISION_SOURCE = "roccho-dev/adrs#233"
EXPECTED_CLASSES = {"accepted-meaning", "merge-admission", "effect", "evidence-only"}


class Error(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_core() -> Any:
    spec = importlib.util.spec_from_file_location("final_ci_topology_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise Error("core-load-failed")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Error(f"invalid-json:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise Error(f"json-not-object:{path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise Error(f"invalid-jsonl:{path}:{exc}") from exc
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Error(f"invalid-jsonl:{path}:{line_no}") from exc
        if not isinstance(row, dict):
            raise Error(f"jsonl-row-not-object:{path}:{line_no}")
        rows.append(row)
    return rows


def require_object(value: Any, code: str, findings: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        findings.append(code)
        return {}
    return value


def inventory_findings(rows: list[dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    meta = [row for row in rows if row.get("kind") == "governance.ciTopologyInventory.meta.v1"]
    workflows = [row for row in rows if row.get("kind") == "governance.ciTopologyInventory.workflow.v1"]
    if len(meta) != 1:
        findings.append("meta-cardinality")
        selected_meta: dict[str, Any] = {}
    else:
        selected_meta = meta[0]
    if selected_meta.get("issue") != "roccho-dev/governance#150":
        findings.append("meta-issue-mismatch")
    if selected_meta.get("parentDecision") != EXPECTED_DECISION_SOURCE:
        findings.append("meta-parent-decision-mismatch")
    if selected_meta.get("currentWorkflowCount") != len(workflows) or len(workflows) != 12:
        findings.append("meta-current-workflow-count-mismatch")
    if selected_meta.get("targetWorkflowCount") != 2:
        findings.append("meta-target-workflow-count-mismatch")

    by_path = {row.get("path"): row for row in workflows if isinstance(row.get("path"), str)}
    if len(by_path) != len(workflows):
        findings.append("workflow-path-duplicate-or-missing")

    merge_targets: list[str] = []
    target_workflows: set[str] = set()
    for path, row in by_path.items():
        target_class = row.get("targetAuthorityClass")
        target_workflow = row.get("targetWorkflow")
        if target_class not in EXPECTED_CLASSES:
            findings.append(f"target-authority-class-unknown:{path}")
        if target_class in {"accepted-meaning", "effect"}:
            findings.append(f"governance-target-authority-forbidden:{path}:{target_class}")
        if target_class == "merge-admission":
            merge_targets.append(path)
        if target_workflow is not None:
            target_workflows.add(str(target_workflow))
        responsibilities = row.get("responsibilities")
        if not isinstance(responsibilities, list) or not responsibilities or any(not isinstance(item, str) or not item for item in responsibilities):
            findings.append(f"responsibilities-invalid:{path}")

    if merge_targets != [GATE_PATH]:
        findings.append("merge-admission-target-not-exact-gate")
    gate = by_path.get(GATE_PATH, {})
    if gate.get("targetWorkflow") != "gov-gate":
        findings.append("gate-target-workflow-mismatch")
    for path, row in by_path.items():
        if path != GATE_PATH and row.get("targetAuthorityClass") != "evidence-only":
            findings.append(f"non-gate-target-authority-not-evidence:{path}")
        if row.get("targetWorkflow") == "gov-canary" and row.get("targetAuthorityClass") != "evidence-only":
            findings.append(f"canary-target-authority-not-evidence:{path}")
    if target_workflows != {"gov-gate", "gov-canary"}:
        findings.append("target-workflow-set-mismatch")
    return sorted(set(findings))


def packet_findings(raw: dict[str, Any], candidate_sha: str, core: Any) -> list[str]:
    findings: list[str] = []
    if raw.get("kind") != "governance.finalCiGate.input.v1":
        findings.append("packet-kind-mismatch")
    if raw.get("repository") != EXPECTED_REPOSITORY:
        findings.append("fixture-repository-mismatch")

    decision = require_object(raw.get("decision"), "decision-not-object", findings)
    if decision.get("source") != EXPECTED_DECISION_SOURCE:
        findings.append("decision-source-mismatch")
    if decision.get("status") != "proposed-fixture":
        findings.append("decision-status-mismatch")
    if decision.get("acceptedReleaseDigest") is not None:
        findings.append("fixture-accepted-release-present")

    for field in ("source", "engine", "candidate", "closure", "authorityModel", "stageSecurity", "lifecycle", "effect", "claims"):
        require_object(raw.get(field), f"{field}-not-object", findings)
    for field in ("receipts", "artifacts"):
        if not isinstance(raw.get(field), list):
            findings.append(f"{field}-not-list")

    authority = raw.get("authorityModel") if isinstance(raw.get("authorityModel"), dict) else {}
    classes = authority.get("classes")
    if not isinstance(classes, list) or len(classes) != len(EXPECTED_CLASSES) or set(classes) != EXPECTED_CLASSES:
        findings.append("authority-class-set-incomplete")

    evaluation_date = raw.get("evaluationDate")
    if not isinstance(evaluation_date, str):
        findings.append("evaluation-date-invalid")
    else:
        try:
            date.fromisoformat(evaluation_date)
        except ValueError:
            findings.append("evaluation-date-invalid")

    try:
        report = core.evaluate(copy.deepcopy(raw), candidate_sha, core.inventory(INVENTORY))
    except Exception as exc:  # fail closed around the pre-acceptance evaluator surface
        findings.append(f"core-evaluator-exception:{type(exc).__name__}")
    else:
        if report.get("status") != "pass" or report.get("decision") != "fixture-pass":
            findings.append("core-evaluator-not-pass")
        if report.get("productionAdmission") is not False:
            findings.append("core-production-admission-overclaim")
        if report.get("allRepositoriesEnforced") is not False:
            findings.append("core-all-repositories-overclaim")
    return sorted(set(findings))


def check(inventory_path: Path, packet_path: Path, candidate_sha: str) -> dict[str, Any]:
    core = load_core()
    inventory_errors = inventory_findings(read_jsonl(inventory_path))
    packet_errors = packet_findings(read_json(packet_path), candidate_sha, core)
    findings = sorted(set(inventory_errors + packet_errors))
    return {
        "kind": "governance.finalCiTopologyHardening.report.v1",
        "status": "fail" if findings else "pass",
        "authority": False,
        "authorityClass": "evidence-only",
        "candidateSha": candidate_sha,
        "findings": findings,
        "productionAdmission": False,
        "allRepositoriesEnforced": False,
        "boundary": "Pre-acceptance hardening only. It binds the fixture to governance #150 and ADRS #233, enforces the exact authority-class set, and cannot perform cutover or effects.",
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")


def selftest(inventory_path: Path, packet_path: Path) -> dict[str, Any]:
    sha = "a" * 40
    base_inventory = read_jsonl(inventory_path)
    base_packet = read_json(packet_path)
    positive = check(inventory_path, packet_path, sha)
    if positive["status"] != "pass":
        raise Error(canonical(positive))

    packet_cases: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = [
        ("decision-source", "decision-source-mismatch", lambda value: value["decision"].update(source="roccho-dev/adrs#other")),
        ("repository", "fixture-repository-mismatch", lambda value: value.update(repository="other/repo")),
        ("class-set", "authority-class-set-incomplete", lambda value: value["authorityModel"].update(classes=["evidence-only"])),
        ("evaluation-date", "evaluation-date-invalid", lambda value: value.update(evaluationDate="not-a-date")),
        ("authority-object", "authorityModel-not-object", lambda value: value.update(authorityModel="bad")),
    ]
    inventory_cases: list[tuple[str, str, Callable[[list[dict[str, Any]]], None]]] = []

    def gate_to_evidence(rows: list[dict[str, Any]]) -> None:
        next(row for row in rows if row.get("path") == GATE_PATH)["targetAuthorityClass"] = "evidence-only"

    def canary_to_merge(rows: list[dict[str, Any]]) -> None:
        next(row for row in rows if row.get("targetWorkflow") == "gov-canary")["targetAuthorityClass"] = "merge-admission"

    def governance_to_meaning(rows: list[dict[str, Any]]) -> None:
        next(row for row in rows if row.get("path") == ".github/workflows/ci.yml")["targetAuthorityClass"] = "accepted-meaning"

    def wrong_current_count(rows: list[dict[str, Any]]) -> None:
        next(row for row in rows if row.get("kind") == "governance.ciTopologyInventory.meta.v1")["currentWorkflowCount"] = 11

    inventory_cases.extend([
        ("gate-target", "merge-admission-target-not-exact-gate", gate_to_evidence),
        ("canary-authority", "merge-admission-target-not-exact-gate", canary_to_merge),
        ("meaning-authority", "governance-target-authority-forbidden:.github/workflows/ci.yml:accepted-meaning", governance_to_meaning),
        ("workflow-count", "meta-current-workflow-count-mismatch", wrong_current_count),
    ])

    results: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        for name, expected, mutate in packet_cases:
            packet = copy.deepcopy(base_packet)
            mutate(packet)
            packet_file = root / f"packet-{name}.json"
            packet_file.write_text(canonical(packet), encoding="utf-8")
            report = check(inventory_path, packet_file, sha)
            if report["status"] != "fail" or expected not in report["findings"]:
                raise Error(canonical({"case": name, "expected": expected, "report": report}))
            results.append({"case": name, "expectedFinding": expected, "status": "pass"})
        for name, expected, mutate in inventory_cases:
            rows = copy.deepcopy(base_inventory)
            mutate(rows)
            inventory_file = root / f"inventory-{name}.jsonl"
            write_jsonl(inventory_file, rows)
            report = check(inventory_file, packet_path, sha)
            if report["status"] != "fail" or expected not in report["findings"]:
                raise Error(canonical({"case": name, "expected": expected, "report": report}))
            results.append({"case": name, "expectedFinding": expected, "status": "pass"})

    return {
        "kind": "governance.finalCiTopologyHardening.selftest.v1",
        "status": "pass",
        "authority": False,
        "positiveCases": 1,
        "destructiveCases": len(results),
        "cases": results,
        "productionAdmission": False,
        "allRepositoriesEnforced": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["check", "selftest"])
    parser.add_argument("--inventory", type=Path, default=INVENTORY)
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--candidate-sha", default="a" * 40)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = selftest(args.inventory, args.packet) if args.command == "selftest" else check(args.inventory, args.packet, args.candidate_sha)
    except Error as exc:
        report = {"kind": "governance.finalCiTopologyHardening.error.v1", "status": "fail", "authority": False, "error": str(exc)}
    print(canonical(report) if args.json else f"final-ci-topology-hardening:{report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
