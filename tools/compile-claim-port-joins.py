#!/usr/bin/env python3
"""Compile normalized claim-port rows into governance organization admissions."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ACTIVE = "organization-active"
BLOCKING_LIFECYCLES = {"pending", "deprecated", "superseded", "conflicting", "revoked"}


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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def string(row: dict[str, Any], field: str, default: str | None = None) -> str | None:
    value = row.get(field, default)
    if isinstance(value, str) and value:
        return value
    return default


def index_unique(rows: list[dict[str, Any]], label: str) -> tuple[dict[str, dict[str, Any]], set[str]]:
    index: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for row in rows:
        subject = string(row, "subjectId")
        if subject is None:
            raise SystemExit(f"{label}: subjectId is required")
        if subject in index:
            duplicates.add(subject)
        index[subject] = row
    return index, duplicates


def receipt_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        subject = string(row, "subjectId")
        if subject is None:
            raise SystemExit("receipts: subjectId is required")
        index[subject] = row
    return index


def admission(
    subject: str,
    result: str,
    *,
    grant: dict[str, Any] | None = None,
    assertion: dict[str, Any] | None = None,
    receipt: dict[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    bundle_matches = True
    closure_matches = True
    required_receipt = receipt is not None
    lifecycle = "active"
    if grant is not None and assertion is not None:
        bundle_matches = string(grant, "acceptedBundleDigest") == string(assertion, "acceptedBundleDigest")
        closure_matches = string(grant, "sourceClosureDigest") == string(assertion, "sourceClosureDigest")
        lifecycle = string(assertion, "lifecycle", string(grant, "lifecycle", "active")) or "active"
    if receipt is not None:
        if grant is not None:
            bundle_matches = bundle_matches and string(receipt, "acceptedBundleDigest") == string(grant, "acceptedBundleDigest")
            closure_matches = closure_matches and string(receipt, "sourceClosureDigest") == string(grant, "sourceClosureDigest")
        required_receipt = True
    return {
        "kind": "governance.organizationAdmission.v1",
        "subjectId": subject,
        "claimClass": "downstream-assertion" if assertion else "accepted-upstream-grant",
        "admissionResult": result,
        "acceptedBundleMatches": bundle_matches,
        "sourceClosureMatches": closure_matches,
        "sourceClosureHeadMatches": True,
        "requiredReceiptPresent": required_receipt,
        "viewDigestAccepted": True,
        "lifecycle": lifecycle,
        "grantId": string(grant or {}, "grantId"),
        "assertionId": string(assertion or {}, "assertionId"),
        "receiptId": string(receipt or {}, "receiptId"),
        "diagnostic": reason or result,
    }


def compile_admissions(
    grants: list[dict[str, Any]],
    assertions: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grant_by_subject, grant_dupes = index_unique(grants, "grants")
    assertion_by_subject, assertion_dupes = index_unique(assertions, "assertions")
    receipt_by_subject = receipt_index(receipts)
    subjects = sorted(set(grant_by_subject) | set(assertion_by_subject) | set(receipt_by_subject) | grant_dupes | assertion_dupes)
    rows: list[dict[str, Any]] = []
    for subject in subjects:
        grant = grant_by_subject.get(subject)
        assertion = assertion_by_subject.get(subject)
        receipt = receipt_by_subject.get(subject)
        if subject in grant_dupes or subject in assertion_dupes:
            rows.append(admission(subject, "conflict", grant=grant, assertion=assertion, receipt=receipt, reason="duplicate-subject"))
            continue
        if grant is None:
            rows.append(admission(subject, "orphan-assertion", assertion=assertion, receipt=receipt))
            continue
        if assertion is None:
            rows.append(admission(subject, "unclaimed-grant", grant=grant, receipt=receipt))
            continue
        lifecycle = string(assertion, "lifecycle", string(grant, "lifecycle", "active")) or "active"
        if lifecycle == "revoked":
            rows.append(admission(subject, "revoked-grant", grant=grant, assertion=assertion, receipt=receipt))
            continue
        if lifecycle in BLOCKING_LIFECYCLES:
            rows.append(admission(subject, "conflict", grant=grant, assertion=assertion, receipt=receipt, reason="blocking-lifecycle"))
            continue
        if string(grant, "acceptedBundleDigest") != string(assertion, "acceptedBundleDigest"):
            rows.append(admission(subject, "stale-assertion", grant=grant, assertion=assertion, receipt=receipt, reason="accepted-bundle-mismatch"))
            continue
        if string(grant, "sourceClosureDigest") != string(assertion, "sourceClosureDigest"):
            rows.append(admission(subject, "stale-assertion", grant=grant, assertion=assertion, receipt=receipt, reason="source-closure-mismatch"))
            continue
        if receipt is None:
            rows.append(admission(subject, "asserted-but-unproven", grant=grant, assertion=assertion, receipt=receipt))
            continue
        if string(receipt, "acceptedBundleDigest") != string(grant, "acceptedBundleDigest"):
            rows.append(admission(subject, "stale-assertion", grant=grant, assertion=assertion, receipt=receipt, reason="receipt-bundle-mismatch"))
            continue
        if string(receipt, "sourceClosureDigest") != string(grant, "sourceClosureDigest"):
            rows.append(admission(subject, "stale-assertion", grant=grant, assertion=assertion, receipt=receipt, reason="receipt-source-closure-mismatch"))
            continue
        rows.append(admission(subject, ACTIVE, grant=grant, assertion=assertion, receipt=receipt))
    return rows


def selftest() -> None:
    base_grant = {
        "kind": "governance.claimPort.upstreamGrant.v1",
        "subjectId": "repo:governance",
        "grantId": "grant:minimal",
        "acceptedBundleDigest": "sha256:bundle",
        "sourceClosureDigest": "sha256:closure",
        "lifecycle": "active",
    }
    base_assertion = {
        "kind": "governance.claimPort.downstreamAssertion.v1",
        "subjectId": "repo:governance",
        "assertionId": "assert:minimal",
        "acceptedBundleDigest": "sha256:bundle",
        "sourceClosureDigest": "sha256:closure",
        "lifecycle": "active",
    }
    base_receipt = {
        "kind": "governance.claimPort.receipt.v1",
        "subjectId": "repo:governance",
        "receiptId": "receipt:minimal",
        "acceptedBundleDigest": "sha256:bundle",
        "sourceClosureDigest": "sha256:closure",
    }
    cases = [
        ([base_grant], [base_assertion], [base_receipt], ACTIVE),
        ([], [base_assertion], [base_receipt], "orphan-assertion"),
        ([base_grant], [], [], "unclaimed-grant"),
        ([base_grant], [base_assertion], [], "asserted-but-unproven"),
        ([base_grant], [dict(base_assertion, sourceClosureDigest="sha256:old")], [base_receipt], "stale-assertion"),
        ([base_grant], [dict(base_assertion, lifecycle="revoked")], [base_receipt], "revoked-grant"),
        ([base_grant], [base_assertion, dict(base_assertion, assertionId="assert:duplicate")], [base_receipt], "conflict"),
    ]
    for grants, assertions, receipts, expected in cases:
        rows = compile_admissions(grants, assertions, receipts)
        if rows[0]["admissionResult"] != expected:
            raise SystemExit(json.dumps({"expected": expected, "rows": rows}, indent=2, sort_keys=True))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_jsonl(root / "grants.jsonl", [base_grant])
        write_jsonl(root / "assertions.jsonl", [base_assertion])
        write_jsonl(root / "receipts.jsonl", [base_receipt])
        rows = compile_admissions(read_jsonl(root / "grants.jsonl"), read_jsonl(root / "assertions.jsonl"), read_jsonl(root / "receipts.jsonl"))
        write_jsonl(root / "admissions.jsonl", rows)
        if not (root / "admissions.jsonl").read_text(encoding="utf-8").strip():
            raise SystemExit("selftest admission output missing")
    print(json.dumps({"status": "claim-port-join-compiler-selftest-pass"}, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["compile", "selftest"], default="compile")
    parser.add_argument("--grants", type=Path)
    parser.add_argument("--assertions", type=Path)
    parser.add_argument("--receipts", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--require-active", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        selftest()
        return 0
    if args.grants is None or args.assertions is None or args.receipts is None or args.out is None:
        parser.error("compile requires --grants --assertions --receipts --out")
    rows = compile_admissions(read_jsonl(args.grants), read_jsonl(args.assertions), read_jsonl(args.receipts))
    write_jsonl(args.out, rows)
    if args.require_active and any(row["admissionResult"] != ACTIVE for row in rows):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
