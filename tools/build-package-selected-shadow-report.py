#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs" / "final-scope-purpose-join"
UNIVERSE = BASE / "selected-universe.jsonl"
BURN_DOWN = BASE / "selected-shadow-burn-down.jsonl"
REPORT = BASE / "selected-shadow-report.json"
FINAL_CHECK_NAME = "gov-final-scope-purpose-join / gate"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_text(text: str) -> str:
    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()


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


def build_report(universe_path: Path = UNIVERSE, burn_down_path: Path = BURN_DOWN) -> dict[str, Any]:
    universe_text = universe_path.read_text(encoding="utf-8")
    burn_text = burn_down_path.read_text(encoding="utf-8")
    universe = read_jsonl(universe_path)
    burn_down = read_jsonl(burn_down_path)
    findings: list[dict[str, Any]] = []

    by_repo = {row.get("repoId"): row for row in universe if isinstance(row.get("repoId"), str)}
    burn_by_repo = {row.get("repoId"): row for row in burn_down if isinstance(row.get("repoId"), str)}

    for row in universe:
        repo_id = row.get("repoId")
        if row.get("kind") != "governance.selectedUniverseRepo.v1":
            findings.append(finding("selected-universe-kind-invalid", "selected universe row kind is invalid", repoId=repo_id))
        if row.get("parent") != "governance#125":
            findings.append(finding("selected-universe-parent-missing", "selected universe row must link governance#125", repoId=repo_id))
        if row.get("status") == "blocking-candidate" and repo_id not in burn_by_repo:
            findings.append(finding("burn-down-row-missing", "blocking candidate needs burn-down row", repoId=repo_id))

    for row in burn_down:
        repo_id = row.get("repoId")
        if repo_id not in by_repo:
            findings.append(finding("burn-down-orphan", "burn-down row has no selected universe row", repoId=repo_id))
        if row.get("authority") is not False:
            findings.append(finding("burn-down-authority-invalid", "burn-down row authority must be false", repoId=repo_id))
        if row.get("disposition") not in {"resolved", "accepted-waiver", "attached-child-issue"}:
            findings.append(finding("burn-down-disposition-invalid", "burn-down disposition is invalid", repoId=repo_id, disposition=row.get("disposition")))
        if not row.get("ownerRef"):
            findings.append(finding("burn-down-owner-ref-missing", "burn-down row must have ownerRef", repoId=repo_id))

    blocking_candidates = [row for row in universe if row.get("status") == "blocking-candidate"]
    unresolved = [row for row in burn_down if row.get("severity") == "blocking" and row.get("disposition") == "attached-child-issue"]
    status = "fail" if findings else "report-generated" if blocking_candidates else "pass"

    return {
        "kind": "governance.selectedUniverseShadowReport.v1",
        "status": status,
        "authority": False,
        "parent": "governance#125",
        "phaseParent": "governance#82",
        "shadowIssue": "governance#110",
        "burnDownIssue": "governance#111",
        "finalCheckName": FINAL_CHECK_NAME,
        "selectedRepoCount": len(universe),
        "blockingCandidateCount": len(blocking_candidates),
        "attachedChildIssueCount": len(unresolved),
        "universeDigest": digest_text(universe_text),
        "burnDownDigest": digest_text(burn_text),
        "findings": findings,
        "rows": universe,
        "burnDownRows": burn_down,
        "rule": "shadow report exposes selected real repo gaps without becoming merge authority; blocking candidates yield report-generated, not pass",
        "boundary": "This is observation and burn-down routing evidence. It does not close selected real package closure-pass and does not change branch protection.",
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def selftest() -> dict[str, Any]:
    report = build_report()
    checked = read_json(REPORT)
    if checked != report:
        raise SystemExit(canonical({"status": "fail", "reason": "checked shadow report does not match generated report", "expected": report, "actual": checked}))
    if report["status"] != "report-generated":
        raise SystemExit(canonical(report))
    if report["blockingCandidateCount"] <= 0:
        raise SystemExit(canonical({"status": "fail", "reason": "shadow must expose blocking candidates", "report": report}))
    if report["attachedChildIssueCount"] != report["blockingCandidateCount"]:
        raise SystemExit(canonical({"status": "fail", "reason": "every blocking candidate must be routed", "report": report}))
    if report["authority"] is not False:
        raise SystemExit(canonical({"status": "fail", "reason": "report must be non-authority"}))
    return {
        "kind": "governance.selectedUniverseShadowReport.selftest.v1",
        "status": "pass",
        "authority": False,
        "shadowStatus": report["status"],
        "blockingCandidateCount": report["blockingCandidateCount"],
        "attachedChildIssueCount": report["attachedChildIssueCount"],
        "reportArtifact": REPORT.relative_to(ROOT).as_posix(),
        "boundary": report["boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build selected universe shadow report.")
    parser.add_argument("command", nargs="?", choices=["build", "selftest"], default="build")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.command == "selftest":
        report = selftest()
    else:
        report = build_report()
        if args.out:
            write_report(args.out, report)
    print(canonical(report) if args.json else f"selected-shadow-report:{report['status']}")
    return 0 if report["status"] in {"pass", "report-generated"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
