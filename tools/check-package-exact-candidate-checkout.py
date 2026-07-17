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

    required = {
        "exact-checkout-ref": f"ref: {CANDIDATE_EXPRESSION}",
        "exact-candidate-env": f"CANDIDATE_SHA: {CANDIDATE_EXPRESSION}",
        "checkout-credentials-disabled": "persist-credentials: false",
        "read-only-permission": "contents: read",
        "stable-job-name": "name: gate",
    }
    for code, fragment in required.items():
        if fragment not in text:
            findings.append(code)
    if text.count(f"ref: {CANDIDATE_EXPRESSION}") != 1:
        findings.append("exact-checkout-ref-cardinality")
    if text.count(f"CANDIDATE_SHA: {CANDIDATE_EXPRESSION}") != 1:
        findings.append("exact-candidate-env-cardinality")
    if "persist-credentials: true" in text:
        findings.append("checkout-credentials-persisted")

    return {
        "kind": "governance.exactCandidateCheckout.report.v1",
        "status": "fail" if findings else "pass",
        "authority": False,
        "authorityClass": "evidence-only",
        "candidateExpression": CANDIDATE_EXPRESSION,
        "findings": sorted(set(findings)),
        "boundary": "The stable fixture evaluates the exact candidate tree it names. Integration coverage remains a separate evidence concern and this checker grants no merge authority.",
    }


def selftest(path: Path = WORKFLOW) -> dict[str, Any]:
    positive = check(path)
    if positive["status"] != "pass":
        raise SystemExit(canonical(positive))
    base = path.read_text(encoding="utf-8")
    cases = [
        ("merge-ref", "exact-checkout-ref", base.replace(f"          ref: {CANDIDATE_EXPRESSION}\n", "")),
        ("persist-token", "checkout-credentials-disabled", base.replace("persist-credentials: false", "persist-credentials: true")),
        ("wrong-env", "exact-candidate-env", base.replace(f"CANDIDATE_SHA: {CANDIDATE_EXPRESSION}", "CANDIDATE_SHA: ${{ github.sha }}")),
        ("write-permission", "read-only-permission", base.replace("contents: read", "contents: write")),
    ]
    results = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for name, expected, text in cases:
            fixture = Path(temp_dir) / f"{name}.yml"
            fixture.write_text(text, encoding="utf-8")
            report = check(fixture)
            if report["status"] != "fail" or expected not in report["findings"]:
                raise SystemExit(canonical({"case": name, "expected": expected, "report": report}))
            results.append({"case": name, "expectedFinding": expected, "status": "pass"})
    return {
        "kind": "governance.exactCandidateCheckout.selftest.v1",
        "status": "pass",
        "authority": False,
        "positiveCases": 1,
        "destructiveCases": len(results),
        "cases": results,
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
