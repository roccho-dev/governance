#!/usr/bin/env python3
"""Deterministic selected-repo claim-check adoption monitor."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "fixtures" / "claim-check-adoption-monitor" / "cases.jsonl"

CHECKS = [
    ("snapshotPresent", "missing-selected-repo", "selected repo snapshot is missing", "governance"),
    ("hasGovernanceInput", "missing-gov-input", "governance checker input is missing", "feat"),
    ("hasClaimAdmissionCheck", "missing-claim-admission-check", "claim admission check is missing", "feat"),
    ("hasCiIntent", "missing-ci-intent", "claim admission CI intent is missing", "feat"),
    ("hasDownstreamClaimSurface", "missing-downstream-claim-surface", "downstream claim surface is missing", "feat"),
    ("hasReceiptSurface", "missing-receipt-surface", "receipt surface is missing", "feat"),
]


def canonical(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        raise SystemExit(f"missing input: {path}")
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


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")


def required_bool(row: dict[str, Any], field: str) -> bool:
    value = row.get(field)
    if not isinstance(value, bool):
        raise SystemExit(f"{row.get('caseId', '<case>')}: {field} must be boolean")
    return value


def diagnostic(row: dict[str, Any], code: str, message: str, owner: str, severity: str = "fail") -> dict[str, Any]:
    return {
        "kind": "governance.claimCheckAdoption.diagnostic.v1",
        "caseId": row["caseId"],
        "selectedUniverseId": row["selectedUniverseId"],
        "repo": row["repo"],
        "diagnosticClass": code,
        "severity": severity,
        "likelyOwner": owner,
        "nextAction": message,
        "authority": False,
    }


def evaluate(row: dict[str, Any]) -> list[dict[str, Any]]:
    for field in ["caseId", "selectedUniverseId", "repo"]:
        if not isinstance(row.get(field), str) or not row[field]:
            raise SystemExit(f"case row requires non-empty {field}")
    if required_bool(row, "selected") is not True:
        return [diagnostic(row, "not-selected", "repo is outside selected universe", "governance", "pass")]

    findings: list[dict[str, Any]] = []
    for field, code, message, owner in CHECKS:
        if required_bool(row, field) is not True:
            findings.append(diagnostic(row, code, message, owner))

    if required_bool(row, "requiresStrict") and required_bool(row, "strictMode") is not True:
        findings.append(diagnostic(row, "warning-only-escape", "selected repo requires strict claim admission mode", "feat"))
    if required_bool(row, "governanceRefFresh") is not True:
        findings.append(diagnostic(row, "stale-gov-ref", "governance checker reference is stale", "feat"))

    if not findings:
        findings.append(diagnostic(row, "adoption-ok", "selected repo keeps the required claim admission check", "none", "pass"))
    return findings


def check_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in cases:
        findings = evaluate(row)
        expected = row.get("expectedDiagnosticClasses")
        if not isinstance(expected, list) or not all(isinstance(item, str) for item in expected):
            raise SystemExit(f"{row.get('caseId', '<case>')}: expectedDiagnosticClasses must be string list")
        actual = sorted(item["diagnosticClass"] for item in findings)
        if actual != sorted(expected):
            raise SystemExit(json.dumps({"caseId": row.get("caseId"), "expected": sorted(expected), "actual": actual, "findings": findings}, indent=2, sort_keys=True))
        output.extend(findings)
    return output


def selftest() -> int:
    cases = read_jsonl(DEFAULT_CASES)
    rows = check_cases(cases)
    classes = {row["diagnosticClass"] for row in rows}
    required = {
        "adoption-ok",
        "missing-gov-input",
        "missing-claim-admission-check",
        "warning-only-escape",
        "stale-gov-ref",
        "missing-ci-intent",
        "missing-selected-repo",
        "missing-downstream-claim-surface",
        "missing-receipt-surface",
    }
    missing = sorted(required - classes)
    if missing:
        raise SystemExit(f"missing fixture coverage: {missing}")
    print(json.dumps({"kind": "governance.claimCheckAdoptionMonitor.selftest.v1", "status": "pass", "caseCount": len(cases)}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["check", "selftest"], default="check")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return selftest()
    findings = check_cases(read_jsonl(args.cases))
    if args.out:
        write_jsonl(args.out, findings)
    else:
        for row in findings:
            print(canonical(row))
    return 1 if any(row.get("severity") == "fail" for row in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
