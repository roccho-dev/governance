#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "fixtures" / "ops-adoption-check-selected-universe" / "cases.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def diagnostic(row: dict) -> str:
    if not row["opsSelected"]:
        return "ops-not-selected"
    if not row["hasClaimAdmissionCheck"]:
        return "missing-claim-admission-check"
    if row["warningOnly"] and row["upstreamGrantProjection"] == "missing":
        return "warning-only-allowed"
    if row["warningOnly"]:
        return "warning-only-blocked"
    return "ops-adoption-ok"


def selftest() -> int:
    cases = read_jsonl(DEFAULT_CASES)
    seen = set()
    for row in cases:
        actual = diagnostic(row)
        expected = row["expectedDiagnosticClasses"]
        if expected != [actual]:
            raise SystemExit(json.dumps({"caseId": row["caseId"], "expected": expected, "actual": actual}, sort_keys=True))
        seen.add(actual)
    required = {"ops-adoption-ok", "missing-claim-admission-check", "warning-only-allowed", "warning-only-blocked", "ops-not-selected"}
    missing = sorted(required - seen)
    if missing:
        raise SystemExit(json.dumps({"missing": missing}, sort_keys=True))
    print(json.dumps({"kind": "governance.opsClaimAdoptionSelectedUniverse.selftest.v1", "status": "pass", "caseCount": len(cases)}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=["check", "selftest"], default="check")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    args = parser.parse_args()
    if args.command == "selftest":
        return selftest()
    for row in read_jsonl(args.cases):
        print(json.dumps({"kind": "governance.opsClaimAdoption.diagnostic.v1", "caseId": row["caseId"], "repo": "ops", "diagnosticClass": diagnostic(row), "authority": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
