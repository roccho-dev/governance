#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADMISSIONS = ROOT / "fixtures" / "central-claim-drift-report" / "admissions.jsonl"

OWNER_ACTION = {
    "adrs-lagging-feat": ("adrs", "map assertion to grant or reject it"),
    "feat-lagging-adrs": ("feat", "add downstream assertion for accepted grant"),
    "claim-unproven": ("feat", "attach required receipt"),
    "claim-stale": ("feat", "refresh assertion and receipt digests"),
    "claim-conflict": ("governance", "preserve conflict for decision"),
    "claim-revoked": ("feat", "retire downstream assertion"),
    "organization-active": ("none", "no action"),
}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def emit(row: dict) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def text(row: dict, field: str, default: str = "") -> str:
    value = row.get(field, default)
    return value if isinstance(value, str) and value else default


def build_report(admissions: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in admissions:
        if row.get("kind") != "governance.organizationAdmission.v1":
            raise SystemExit("row kind must be governance.organizationAdmission.v1")
        key = (
            text(row, "selectedUniverseId", "selected-repos:unknown"),
            text(row, "repo", text(row, "subjectId", "repo:unknown").split(":", 1)[-1]),
            text(row, "subjectId"),
            text(row, "contractId", text(row, "grantId", "contract:unknown")),
            text(row, "admissionResult"),
            text(row, "diagnosticClass"),
        )
        grouped[key].append(row)

    out = []
    for key, rows in grouped.items():
        selected_universe, repo, subject_id, contract_id, admission_result, diagnostic_class = key
        owner, action = OWNER_ACTION.get(diagnostic_class, ("governance", "inspect diagnostic"))
        out.append({
            "kind": "governance.centralClaimDrift.group.v1",
            "selectedUniverseId": selected_universe,
            "repo": repo,
            "subjectId": subject_id,
            "contractId": contract_id,
            "admissionResult": admission_result,
            "diagnosticClass": diagnostic_class,
            "likelyOwner": owner,
            "nextAction": action,
            "count": len(rows),
            "authority": False,
        })
    return sorted(out, key=emit)


def selftest() -> int:
    report = build_report(read_jsonl(DEFAULT_ADMISSIONS))
    classes = {row["diagnosticClass"] for row in report}
    required = {"adrs-lagging-feat", "feat-lagging-adrs", "claim-unproven", "claim-stale"}
    missing = sorted(required - classes)
    if missing:
        raise SystemExit(json.dumps({"missing": missing}, sort_keys=True))
    if len([row for row in report if row["diagnosticClass"] in required]) != 4:
        raise SystemExit(json.dumps({"message": "required classes must stay distinct", "report": report}, sort_keys=True))
    print(json.dumps({"kind": "governance.centralClaimDriftReport.selftest.v1", "status": "pass", "groupCount": len(report)}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=["build", "selftest"], default="build")
    parser.add_argument("--admissions", type=Path, default=DEFAULT_ADMISSIONS)
    args = parser.parse_args()
    if args.command == "selftest":
        return selftest()
    for row in build_report(read_jsonl(args.admissions)):
        print(emit(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
