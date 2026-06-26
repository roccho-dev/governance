#!/usr/bin/env python3
"""Deterministic production gate for organization admission views.

The check is intentionally narrow: official views may include only subjects
whose admission record resolves to organization-active through checked-in
inputs. Latest user/operator intent is accepted as a non-authority claim class
that can challenge the join, not as authority by itself.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_CLAIM_CLASSES = {
    "accepted-upstream-grant",
    "downstream-assertion",
    "latest-user-intent",
    "latest-operator-intent",
    "receipt",
    "source-closure",
}

BLOCKING_RESULTS = {
    "orphan-assertion",
    "unclaimed-grant",
    "stale-assertion",
    "asserted-but-unproven",
    "conflict",
    "revoked-grant",
}

BLOCKING_LIFECYCLES = {
    "pending",
    "deprecated",
    "superseded",
    "conflicting",
    "revoked",
}


@dataclass(frozen=True)
class Finding:
    code: str
    subject_id: str
    message: str

    def to_json(self) -> dict[str, str]:
        return {
            "code": self.code,
            "subjectId": self.subject_id,
            "message": self.message,
        }


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON {path}: {exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSONL {path}:{line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise SystemExit(f"invalid JSONL {path}:{line_no}: row is not object")
        rows.append(row)
    return rows


def require_string(row: dict[str, Any], field: str, path: Path) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise SystemExit(f"{path}: {field} must be a non-empty string")
    return value


def admission_index(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        subject_id = require_string(row, "subjectId", path)
        if subject_id in index:
            raise SystemExit(f"{path}: duplicate admission for {subject_id}")
        index[subject_id] = row
    return index


def official_subjects(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    subjects = data.get("subjects")
    if not isinstance(subjects, list):
        raise SystemExit(f"{path}: subjects must be a list")
    for item in subjects:
        if not isinstance(item, dict):
            raise SystemExit(f"{path}: subject row is not object")
        require_string(item, "subjectId", path)
    return subjects


def check(admissions_path: Path, official_view_path: Path) -> dict[str, Any]:
    admissions = admission_index(admissions_path)
    subjects = official_subjects(official_view_path)
    findings: list[Finding] = []

    for subject in subjects:
        subject_id = subject["subjectId"]
        row = admissions.get(subject_id)
        if row is None:
            findings.append(Finding("missing-admission", subject_id, "official view subject has no admission record"))
            continue

        claim_class = row.get("claimClass", row.get("sourceClass"))
        if claim_class not in ALLOWED_CLAIM_CLASSES:
            findings.append(Finding("unknown-claim-class", subject_id, "admission source claim class is not recognized"))

        view_result = subject.get("admissionResult", "organization-active")
        row_result = row.get("admissionResult")
        if view_result != "organization-active":
            findings.append(Finding("non-active-in-official-view", subject_id, "official view may only include organization-active subjects"))
        if row_result != "organization-active":
            findings.append(Finding("blocking-admission-result", subject_id, f"admission result is {row_result!r}"))
        if row_result in BLOCKING_RESULTS:
            findings.append(Finding(row_result, subject_id, "blocking diagnostic is present in official view"))

        if row.get("acceptedBundleMatches") is False:
            findings.append(Finding("accepted-bundle-mismatch", subject_id, "accepted bundle digest does not match current admission input"))
        if row.get("sourceClosureMatches") is False:
            findings.append(Finding("source-closure-mismatch", subject_id, "source closure digest does not match current admission input"))
        if row.get("sourceClosureHeadMatches") is False:
            findings.append(Finding("source-closure-head-mismatch", subject_id, "source closure head does not include the latest required input"))
        if row.get("requiredReceiptPresent") is False:
            findings.append(Finding("missing-required-receipt", subject_id, "required evidence receipt is absent"))
        if row.get("duplicateActiveAssertion") is True:
            findings.append(Finding("duplicate-active-assertion", subject_id, "single-owner scope has duplicate active assertions"))
        if row.get("viewDigestAccepted") is False:
            findings.append(Finding("official-view-digest-unaccepted", subject_id, "execution input view digest is not admitted"))

        lifecycle = row.get("lifecycle")
        if lifecycle in BLOCKING_LIFECYCLES:
            findings.append(Finding("blocking-lifecycle", subject_id, f"lifecycle is {lifecycle!r}"))

        if claim_class in {"latest-user-intent", "latest-operator-intent"} and row.get("challengesCurrentAssertion") is True:
            findings.append(Finding("unresolved-latest-intent-challenge", subject_id, "latest intent challenge cannot be admitted as authority"))
        if claim_class in {"latest-user-intent", "latest-operator-intent"}:
            if not isinstance(row.get("scope"), str) or not row["scope"]:
                findings.append(Finding("incomplete-latest-intent-claim", subject_id, "latest intent claim requires scope"))
            if not isinstance(row.get("actor"), str) or not row["actor"]:
                findings.append(Finding("incomplete-latest-intent-claim", subject_id, "latest intent claim requires actor provenance"))
            if not row.get("targetAssertionDigest") and not row.get("targetViewDigest"):
                findings.append(Finding("incomplete-latest-intent-claim", subject_id, "latest intent claim requires a target assertion or view digest"))

    return {
        "kind": "governance.orgAdmissionGate.report.v1",
        "status": "fail" if findings else "pass",
        "findings": [finding.to_json() for finding in findings],
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def expect(admissions: list[dict[str, Any]], subjects: list[dict[str, Any]], should_pass: bool) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        admissions_path = root / "admissions.jsonl"
        official_path = root / "official-view.json"
        write_jsonl(admissions_path, admissions)
        write_json(official_path, {"kind": "governance.officialOrganizationView.v1", "subjects": subjects})
        report = check(admissions_path, official_path)
        passed = report["status"] == "pass"
        if passed != should_pass:
            raise SystemExit(json.dumps(report, indent=2))


def selftest() -> None:
    active = {
        "kind": "governance.organizationAdmission.v1",
        "subjectId": "repo:active",
        "claimClass": "accepted-upstream-grant",
        "admissionResult": "organization-active",
        "acceptedBundleMatches": True,
        "sourceClosureMatches": True,
        "requiredReceiptPresent": True,
        "sourceClosureHeadMatches": True,
        "viewDigestAccepted": True,
        "lifecycle": "active",
    }
    expect([active], [{"subjectId": "repo:active", "admissionResult": "organization-active"}], True)

    for result in ("stale-assertion", "asserted-but-unproven", "conflict"):
        row = dict(active, subjectId=f"repo:{result}", admissionResult=result)
        expect([row], [{"subjectId": row["subjectId"], "admissionResult": "organization-active"}], False)

    challenged = dict(
        active,
        subjectId="repo:latest-intent",
        claimClass="latest-user-intent",
        challengesCurrentAssertion=True,
        scope="repo",
        actor="user:test",
        targetAssertionDigest="sha256:old",
    )
    expect([challenged], [{"subjectId": "repo:latest-intent", "admissionResult": "organization-active"}], False)

    mismatch = dict(active, subjectId="repo:mismatch", sourceClosureMatches=False)
    expect([mismatch], [{"subjectId": "repo:mismatch", "admissionResult": "organization-active"}], False)
    closure_head = dict(active, subjectId="repo:closure-head", sourceClosureHeadMatches=False)
    expect([closure_head], [{"subjectId": "repo:closure-head", "admissionResult": "organization-active"}], False)
    duplicate = dict(active, subjectId="repo:duplicate", duplicateActiveAssertion=True)
    expect([duplicate], [{"subjectId": "repo:duplicate", "admissionResult": "organization-active"}], False)
    lifecycle = dict(active, subjectId="repo:lifecycle", lifecycle="superseded")
    expect([lifecycle], [{"subjectId": "repo:lifecycle", "admissionResult": "organization-active"}], False)
    expect([active], [{"subjectId": "repo:missing", "admissionResult": "organization-active"}], False)

    unknown = dict(active, subjectId="repo:unknown", claimClass="policy-drift")
    expect([unknown], [{"subjectId": "repo:unknown", "admissionResult": "organization-active"}], False)
    incomplete_latest = dict(active, subjectId="repo:incomplete-latest", claimClass="latest-user-intent")
    expect([incomplete_latest], [{"subjectId": "repo:incomplete-latest", "admissionResult": "organization-active"}], False)

    print(json.dumps({"status": "org-admission-gate-selftest-pass"}, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["check", "selftest"], default="check")
    parser.add_argument("--admissions", type=Path)
    parser.add_argument("--official-view", type=Path)
    args = parser.parse_args(argv)

    if args.command == "selftest":
        selftest()
        return 0
    if args.admissions is None or args.official_view is None:
        parser.error("check requires --admissions and --official-view")

    report = check(args.admissions, args.official_view)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
