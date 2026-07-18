#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/gov-final-scope-purpose-join.yml"
CANDIDATE_EXPRESSION = "${{ github.event.pull_request.head.sha || github.sha }}"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def check(path: Path = WORKFLOW) -> dict[str, Any]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        findings.append(f"workflow-unreadable:{exc}")
        text = ""

    checkout_count = text.count("uses: actions/checkout@v4")
    credential_count = text.count("persist-credentials: false")
    if checkout_count < 4:
        findings.append("checkout-stage-cardinality")
    if credential_count != checkout_count:
        findings.append("checkout-credentials-not-disabled-everywhere")
    if text.count(f"ref: {CANDIDATE_EXPRESSION}") < 3:
        findings.append("exact-candidate-checkout-missing")
    if text.count(f"CANDIDATE_SHA: {CANDIDATE_EXPRESSION}") < 2:
        findings.append("exact-candidate-env-missing")
    if "pull_request_target" in text:
        findings.append("unsafe-pull-request-target")
    if "persist-credentials: true" in text:
        findings.append("checkout-credentials-persisted")
    if "contents: write" in text:
        findings.append("write-permission")
    if "name: gate" not in text:
        findings.append("stable-gate-name")

    return {
        "kind": "governance.exactCandidateCheckout.report.v2",
        "status": "fail" if findings else "pass",
        "authority": False,
        "authorityClass": "evidence-only",
        "candidateExpression": CANDIDATE_EXPRESSION,
        "checkoutCount": checkout_count,
        "findings": sorted(set(findings)),
        "boundary": "All pull-request candidate execution names and checks the exact head SHA. Push-only post-effect readback binds github.sha separately.",
    }


def selftest(path: Path = WORKFLOW) -> dict[str, Any]:
    positive = check(path)
    if positive["status"] != "pass":
        raise SystemExit(canonical(positive))
    base = path.read_text(encoding="utf-8")
    cases = [
        ("persist-token", "checkout-credentials", base.replace("persist-credentials: false", "persist-credentials: true", 1)),
        ("wrong-env", "exact-candidate-env", base.replace(f"CANDIDATE_SHA: {CANDIDATE_EXPRESSION}", "CANDIDATE_SHA: ${{ github.sha }}", 2)),
        ("unsafe-event", "unsafe-pull-request-target", base.replace("pull_request:", "pull_request_target:")),
        ("write-permission", "write-permission", base.replace("contents: read", "contents: write")),
    ]
    results = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for name, expected, text in cases:
            fixture = Path(temp_dir) / f"{name}.yml"
            fixture.write_text(text, encoding="utf-8")
            report = check(fixture)
            if report["status"] != "fail" or not any(expected in finding for finding in report["findings"]):
                raise SystemExit(canonical({"case": name, "expected": expected, "report": report}))
            results.append({"case": name, "status": "pass"})
    return {"kind": "governance.exactCandidateCheckout.selftest.v2", "status": "pass", "positiveCases": 1, "destructiveCases": len(results), "cases": results, "authority": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=["check", "selftest"], default="check")
    parser.add_argument("--workflow", type=Path, default=WORKFLOW)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = selftest(args.workflow) if args.command == "selftest" else check(args.workflow)
    print(canonical(report) if args.json else f"exact-candidate-checkout:{report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
