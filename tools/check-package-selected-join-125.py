#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "fspj-125" / "manifest.json"


def emit(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def check():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    findings = []
    ids = data.get("expectedIds", [])
    receipts = data.get("requiredReceipts", [])
    if sorted(ids) != ["g", "o", "u"]:
        findings.append("expected-id-set")
    if len(receipts) != 3:
        findings.append("receipt-count")
    if data.get("status") != "ready":
        findings.append("status")
    report = {
        "kind": "fspj125.report.v1",
        "status": "pass" if not findings else "fail",
        "parent": "governance#125",
        "expectedIds": ids,
        "receiptCount": len(receipts),
        "blockingDriftCount": len(findings),
        "findings": findings,
        "boundary": "This verifies the selected join manifest. It is not a meaning source.",
    }
    return report


def selftest():
    report = check()
    if report["status"] != "pass":
        raise SystemExit(emit(report))
    return report


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    report = selftest() if command == "selftest" else check()
    print(emit(report))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
