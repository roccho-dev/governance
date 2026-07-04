#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs" / "final-scope-purpose-join"
PACKET = BASE / "ssot-publish-gate-acceptance.json"
FINAL_CHECK_NAME = "gov-final-scope-purpose-join / gate"
SELECTED_REF = "refs/heads/proposals"
PROVIDER = "bare-repo-ssot-checked-mirror-publish"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(canonical({"status": "fail", "path": str(path), "reason": "json-not-object"}))
    return value


def finding(code: str, message: str, **extra: Any) -> dict[str, Any]:
    row = {"code": code, "message": message}
    row.update(extra)
    return row


def is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value))


def is_digest(value: Any) -> bool:
    return isinstance(value, str) and bool(DIGEST_RE.fullmatch(value))


def validate(packet: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    if packet.get("kind") != "governance.ssotPublishGateAcceptance.v1":
        findings.append(finding("packet-kind-invalid", "packet kind must be governance.ssotPublishGateAcceptance.v1"))
    if packet.get("provider") != PROVIDER:
        findings.append(finding("provider-invalid", "provider must be the selected SSOT publish provider", expected=PROVIDER, actual=packet.get("provider")))
    if packet.get("selectedRef") != SELECTED_REF:
        findings.append(finding("selected-ref-invalid", "selected ref must match the governed ref", expected=SELECTED_REF, actual=packet.get("selectedRef")))
    if packet.get("finalGateName") != FINAL_CHECK_NAME:
        findings.append(finding("final-gate-name-invalid", "final gate name must match emitted workflow check", expected=FINAL_CHECK_NAME, actual=packet.get("finalGateName")))
    if packet.get("authority") is not False:
        findings.append(finding("authority-invalid", "acceptance packet must remain non-authority evidence"))

    rollback = packet.get("rollback") if isinstance(packet.get("rollback"), dict) else {}
    if rollback.get("documented") is not True:
        findings.append(finding("rollback-missing", "rollback instructions must be documented"))
    if not rollback.get("restorePreviousProviderState"):
        findings.append(finding("rollback-restore-missing", "rollback must describe restoring previous provider state"))

    receipts = packet.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        findings.append(finding("receipts-missing", "packet must include receipts"))
        receipts = []

    allow_count = 0
    reject_missing_gate = 0
    reject_stale = 0
    reject_mismatch = 0
    audit_complete = 0

    for idx, receipt in enumerate(receipts):
        if not isinstance(receipt, dict):
            findings.append(finding("receipt-not-object", "receipt must be an object", index=idx))
            continue
        receipt_id = receipt.get("receiptId")
        decision = receipt.get("decision")
        target_sha = receipt.get("targetSha")
        gate = receipt.get("finalGate") if isinstance(receipt.get("finalGate"), dict) else {}
        reasons = receipt.get("reasons") if isinstance(receipt.get("reasons"), list) else []

        if decision not in {"allow", "reject"}:
            findings.append(finding("receipt-decision-invalid", "receipt decision must be allow or reject", receiptId=receipt_id))
        if receipt.get("provider") != PROVIDER:
            findings.append(finding("receipt-provider-invalid", "receipt provider must match selected provider", receiptId=receipt_id))
        if receipt.get("selectedRef") != SELECTED_REF:
            findings.append(finding("receipt-selected-ref-invalid", "receipt selected ref must match", receiptId=receipt_id))
        if not is_sha(target_sha):
            findings.append(finding("receipt-target-sha-invalid", "receipt targetSha must be a 40-char sha", receiptId=receipt_id))
        if not receipt.get("actor"):
            findings.append(finding("receipt-actor-missing", "receipt must record actor", receiptId=receipt_id))
        if not receipt.get("path"):
            findings.append(finding("receipt-path-missing", "receipt must record update path", receiptId=receipt_id))
        if not receipt.get("timestamp"):
            findings.append(finding("receipt-timestamp-missing", "receipt must record timestamp", receiptId=receipt_id))
        if gate.get("name") not in {FINAL_CHECK_NAME, None}:
            findings.append(finding("receipt-final-gate-name-invalid", "receipt final gate name must match or be absent for missing-gate reject", receiptId=receipt_id))
        if gate.get("status") == "pass" and gate.get("targetSha") != target_sha:
            reject_stale += 1
        if gate.get("status") in {None, "missing"}:
            reject_missing_gate += 1
        if "digest-mismatch" in reasons or "target-sha-mismatch" in reasons:
            reject_mismatch += 1
        if is_digest(gate.get("outputDigest")) or decision == "reject":
            audit_complete += 1
        if decision == "allow":
            allow_count += 1
            if gate.get("name") != FINAL_CHECK_NAME:
                findings.append(finding("allow-final-gate-name-invalid", "allow receipt must have final gate name", receiptId=receipt_id))
            if gate.get("status") != "pass":
                findings.append(finding("allow-final-gate-not-pass", "allow receipt must have final gate pass", receiptId=receipt_id))
            if gate.get("targetSha") != target_sha:
                findings.append(finding("allow-target-sha-mismatch", "allow receipt must match exact target SHA", receiptId=receipt_id))
            if not is_digest(gate.get("outputDigest")):
                findings.append(finding("allow-output-digest-missing", "allow receipt must record final gate output digest", receiptId=receipt_id))

    if allow_count < 1:
        findings.append(finding("accept-proof-missing", "at least one exact target SHA allow receipt is required"))
    if reject_missing_gate < 1:
        findings.append(finding("reject-missing-gate-proof-missing", "at least one missing gate reject receipt is required"))
    if reject_stale < 1:
        findings.append(finding("reject-stale-proof-missing", "at least one stale target SHA reject receipt is required"))
    if reject_mismatch < 1:
        findings.append(finding("reject-mismatch-proof-missing", "at least one mismatch reject receipt is required"))
    if audit_complete != len(receipts):
        findings.append(finding("audit-incomplete", "each receipt must carry enough audit data", expected=len(receipts), actual=audit_complete))

    return {
        "kind": "governance.ssotPublishGateAcceptance.report.v1",
        "status": "pass" if not findings else "fail",
        "authority": False,
        "parent": "governance#125",
        "phaseIssue": "governance#115",
        "provider": PROVIDER,
        "selectedRef": SELECTED_REF,
        "finalGateName": FINAL_CHECK_NAME,
        "receiptCount": len(receipts),
        "allowCount": allow_count,
        "rejectMissingGateCount": reject_missing_gate,
        "rejectStaleCount": reject_stale,
        "rejectMismatchCount": reject_mismatch,
        "findings": findings,
        "boundary": "This validates the SSOT publish gate acceptance packet shape. It does not by itself prove external active enforcement unless the packet is populated from a real provider execution log.",
    }


def selftest() -> dict[str, Any]:
    packet = read_json(PACKET)
    report = validate(packet)
    if report["status"] != "pass":
        raise SystemExit(canonical(report))
    return {
        "kind": "governance.ssotPublishGateAcceptance.selftest.v1",
        "status": "pass",
        "authority": False,
        "phaseIssue": "governance#115",
        "provider": PROVIDER,
        "selectedRef": SELECTED_REF,
        "finalGateName": FINAL_CHECK_NAME,
        "report": report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SSOT publish gate acceptance packet evidence.")
    parser.add_argument("command", nargs="?", choices=["check", "selftest"], default="check")
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.command == "selftest":
        report = selftest()
    else:
        report = validate(read_json(args.packet))
    print(canonical(report) if args.json else f"ssot-publish-gate-acceptance:{report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
