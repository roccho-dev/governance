#!/usr/bin/env python3
"""Fixture proof for ports -> admission rows -> official view gate."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def expect_results(admissions: list[dict[str, Any]], expected: dict[str, str]) -> None:
    actual = {row["subjectId"]: row["admissionResult"] for row in admissions}
    for subject, result in expected.items():
        if actual.get(subject) != result:
            raise SystemExit(json.dumps({"expected": expected, "actual": actual}, indent=2, sort_keys=True))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        grants = root / "grants.jsonl"
        assertions = root / "assertions.jsonl"
        receipts = root / "receipts.jsonl"
        admissions = root / "admissions.jsonl"
        write_jsonl(grants, [
            {"kind": "governance.claimPort.upstreamGrant.v1", "subjectId": "repo:active", "grantId": "grant:active", "acceptedBundleDigest": "sha256:bundle-active", "sourceClosureDigest": "sha256:closure-active", "lifecycle": "active"},
            {"kind": "governance.claimPort.upstreamGrant.v1", "subjectId": "repo:unclaimed", "grantId": "grant:unclaimed", "acceptedBundleDigest": "sha256:bundle-unclaimed", "sourceClosureDigest": "sha256:closure-unclaimed", "lifecycle": "active"},
            {"kind": "governance.claimPort.upstreamGrant.v1", "subjectId": "repo:unproven", "grantId": "grant:unproven", "acceptedBundleDigest": "sha256:bundle-unproven", "sourceClosureDigest": "sha256:closure-unproven", "lifecycle": "active"},
            {"kind": "governance.claimPort.upstreamGrant.v1", "subjectId": "repo:stale", "grantId": "grant:stale", "acceptedBundleDigest": "sha256:bundle-stale", "sourceClosureDigest": "sha256:closure-stale", "lifecycle": "active"},
        ])
        write_jsonl(assertions, [
            {"kind": "governance.claimPort.downstreamAssertion.v1", "subjectId": "repo:active", "assertionId": "assertion:active", "acceptedBundleDigest": "sha256:bundle-active", "sourceClosureDigest": "sha256:closure-active", "lifecycle": "active"},
            {"kind": "governance.claimPort.downstreamAssertion.v1", "subjectId": "repo:orphan", "assertionId": "assertion:orphan", "acceptedBundleDigest": "sha256:bundle-orphan", "sourceClosureDigest": "sha256:closure-orphan", "lifecycle": "active"},
            {"kind": "governance.claimPort.downstreamAssertion.v1", "subjectId": "repo:unproven", "assertionId": "assertion:unproven", "acceptedBundleDigest": "sha256:bundle-unproven", "sourceClosureDigest": "sha256:closure-unproven", "lifecycle": "active"},
            {"kind": "governance.claimPort.downstreamAssertion.v1", "subjectId": "repo:stale", "assertionId": "assertion:stale", "acceptedBundleDigest": "sha256:bundle-stale", "sourceClosureDigest": "sha256:closure-old", "lifecycle": "active"},
        ])
        write_jsonl(receipts, [
            {"kind": "governance.claimPort.receipt.v1", "subjectId": "repo:active", "receiptId": "receipt:active", "acceptedBundleDigest": "sha256:bundle-active", "sourceClosureDigest": "sha256:closure-active"},
            {"kind": "governance.claimPort.receipt.v1", "subjectId": "repo:orphan", "receiptId": "receipt:orphan", "acceptedBundleDigest": "sha256:bundle-orphan", "sourceClosureDigest": "sha256:closure-orphan"},
            {"kind": "governance.claimPort.receipt.v1", "subjectId": "repo:stale", "receiptId": "receipt:stale", "acceptedBundleDigest": "sha256:bundle-stale", "sourceClosureDigest": "sha256:closure-stale"},
        ])
        subprocess.run([sys.executable, "tools/compile-claim-port-joins.py", "compile", "--grants", str(grants), "--assertions", str(assertions), "--receipts", str(receipts), "--out", str(admissions)], check=True)
        expect_results(rows(admissions), {
            "repo:active": "organization-active",
            "repo:unclaimed": "unclaimed-grant",
            "repo:orphan": "orphan-assertion",
            "repo:unproven": "asserted-but-unproven",
            "repo:stale": "stale-assertion",
        })
        ok_view = root / "official-pass.json"
        write_json(ok_view, {"kind": "governance.officialOrganizationView.v1", "subjects": [{"subjectId": "repo:active", "admissionResult": "organization-active"}]})
        subprocess.run([sys.executable, "tools/check-org-admission-gate.py", "check", "--admissions", str(admissions), "--official-view", str(ok_view)], check=True)
        bad_view = root / "official-fail.json"
        write_json(bad_view, {"kind": "governance.officialOrganizationView.v1", "subjects": [{"subjectId": "repo:stale", "admissionResult": "organization-active"}]})
        failed = subprocess.run([sys.executable, "tools/check-org-admission-gate.py", "check", "--admissions", str(admissions), "--official-view", str(bad_view)], check=False)
        if failed.returncode == 0:
            raise SystemExit("non-active admission unexpectedly passed official view gate")
    print(json.dumps({"status": "org-admission-join-fixture-proof-pass"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
