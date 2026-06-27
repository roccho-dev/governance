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


def result(row: dict) -> str:
    if row["selected"] != "yes":
        return "not-selected"
    if row["check"] != "yes":
        return "missing-check"
    if row["mode"] == "warn" and row["projection"] == "missing":
        return "temp-warn"
    if row["mode"] == "warn":
        return "strict-needed"
    return "ok"


def selftest() -> int:
    cases = read_jsonl(DEFAULT_CASES)
    seen = set()
    for row in cases:
        actual = result(row)
        if row["expected"] != actual:
            raise SystemExit(json.dumps({"case": row["case"], "expected": row["expected"], "actual": actual}, sort_keys=True))
        seen.add(actual)
    required = {"ok", "missing-check", "temp-warn", "strict-needed", "not-selected"}
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
        print(json.dumps({"kind": "governance.opsClaimAdoption.diagnostic.v1", "case": row["case"], "repo": "ops", "diagnosticClass": result(row), "authority": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
