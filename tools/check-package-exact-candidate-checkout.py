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
    candidate_env_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("CANDIDATE_SHA:")
    ]

    if checkout_count < 4:
        findings.append("checkout-stage-cardinality")
    if credential_count != checkout_count:
        findings.append("checkout-credentials-not-disabled-everywhere")
    if text.count(f"ref: {CANDIDATE_EXPRESSION}") < 3:
        findings.append("exact-candidate-checkout-missing")
    if len(candidate_env_lines) < 2:
        findings.append("exact-candidate-env-missing")
    if any(line != f"CANDIDATE_SHA: {CANDIDATE_EXPRESSION}" for line in candidate_env_lines):
        findings.append("exact-candidate-env-mismatch")
    if "pull_request_target" in text:
        findings.append("unsafe-pull-request-target")
    if "persist-credentials: true" in text:
        findings.append("checkout-credentials-persisted")
    if "contents: write" in text:
        findings.append("write-permission")
    if "name: gate" not in text:
        findings.append("stable-gate-name")

    return {
        "kind": "governance.exactCandidateCheckout.report.v3",
        "status": "fail" if findings else "pass",
        "authority": False,
        "authorityClass": "evidence-only",
        "candidateExpression": CANDIDATE_EXPRESSION,
        "checkoutCount": checkout_count,
        "candidateEnvironmentCount": len(candidate_env_lines),
        "findings": sorted(set(findings)),
        "boundary": "Every declared CANDIDATE_SHA binding uses the exact PR head or pushed SHA. External accepted/candidate source refs remain separately pinned.",
    }


def selftest(path: Path = WORKFLOW) -> dict[str, Any]:
    positive = check(path)
    if positive["status"] != "pass":
        raise SystemExit(canonical(positive))
    base = path.read_text(encoding="utf-8")
    cases = [
        ("persist-token", "checkout-credentials", base.replace("persist-credentials: false", "persist-credentials: true", 1)),
        ("wrong-env", "exact-candidate-env-mismatch", base.replace(f"CANDIDATE_SHA: {CANDIDATE_EXPRESSION}", "CANDIDATE_SHA: ${{ github.sha }}", 1)),
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
    return {
        "kind": "governance.exactCandidateCheckout.selftest.v3",
        "status": "pass",
        "positiveCases": 1,
        "destructiveCases": len(results),
        "cases": results,
        "authority": False,
    }


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
