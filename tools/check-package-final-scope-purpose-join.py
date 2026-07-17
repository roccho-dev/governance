#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FINAL_CHECK_NAME = "gov-final-scope-purpose-join / gate"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def run_component(name: str, args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {"name": name, "status": "pass" if proc.returncode == 0 else "fail", "exitCode": proc.returncode, "output": proc.stdout.strip().splitlines()[-5:]}


def regression_components() -> list[dict[str, Any]]:
    return [
        run_component("package-closure-strict", [sys.executable, "tools/check-package-closure-strict.py", "selftest", "--json"]),
        run_component("required-repo-org-join", [sys.executable, "tools/check-package-required-repo-org-join.py", "selftest"]),
        run_component("provider-ci-yaml", [sys.executable, "tools/check-provider-ci-yaml.py", "selftest"]),
        run_component("merge-write-boundary-final-gate", [sys.executable, "tools/check-merge-write-boundary-final-gate.py", "selftest", "--json"]),
        run_component("fspj-real-join", [sys.executable, "tools/check-package-fspj-real.py"]),
        run_component("exact-candidate-checkout", [sys.executable, "tools/check-package-exact-candidate-checkout.py", "selftest", "--json"]),
        run_component("final-ci-topology-migration-safety", [sys.executable, "tools/check-package-final-ci-topology.py", "selftest", "--json"]),
        run_component("final-ci-topology-hardening", [sys.executable, "tools/check-package-final-ci-topology-hardening.py", "selftest", "--json"]),
    ]


def run_selftest() -> dict[str, Any]:
    components = regression_components()
    failed = [row for row in components if row["status"] != "pass"]
    if failed:
        raise SystemExit(canonical({"kind": "governance.finalScopePurposeJoin.selftest.v1", "status": "fail", "failedComponents": failed}))
    return {
        "kind": "governance.finalScopePurposeJoin.selftest.v1",
        "status": "pass",
        "authority": False,
        "authorityClass": "evidence-only",
        "finalCheckName": FINAL_CHECK_NAME,
        "evidenceMode": "strict-gate-adapter-selftest",
        "components": components,
        "strictFailureCapability": [
            "missing packet source",
            "missing govPackageOutput packet",
            "malformed or handwritten packet",
            "stale packet source revision",
            "invalid producer provenance",
            "packet digest mismatch",
            "missing package inventory or package path",
            "missing package response",
            "missing receipt",
            "non-active admission",
            "provider CI drift",
            "manual or stale provider CI edit",
            "expired waiver",
            "generated artifact misclassified as pass",
            "fspj real join blocking drift",
            "exact candidate SHA mismatch",
            "candidate claim differs from checked-out tree",
            "checkout credential persistence",
            "stale claim or receipt",
            "authority class collision or incomplete class set",
            "wrong merge-admission target",
            "fixture repository or decision-source substitution",
            "incomplete CI responsibility transfer",
            "fixture or fallback offered as production admission",
        ],
        "boundary": "This is the final gate regression surface. ADRS #233 is proposed; no branch-protection cutover, merge-admission authority, effect authority, workflow deletion, or all-repository claim is made.",
    }


def run_check(candidate_sha: str) -> dict[str, Any]:
    selftest = run_selftest()
    hardening = run_component(
        "current-exact-sha-hardening",
        [
            sys.executable,
            "tools/check-package-final-ci-topology-hardening.py",
            "check",
            "--candidate-sha",
            candidate_sha,
            "--json",
        ],
    )
    gate = run_component(
        "current-exact-sha-non-authority-fixture",
        [
            sys.executable,
            "tools/check-package-final-ci-topology.py",
            "gate",
            "--candidate-sha",
            candidate_sha,
            "--json",
        ],
    )
    failed = [row for row in (hardening, gate) if row["status"] != "pass"]
    if failed:
        raise SystemExit(canonical({"kind": "governance.finalScopePurposeJoin.fixtureCheck.v1", "status": "fail", "failedComponents": failed}))
    return {
        "kind": "governance.finalScopePurposeJoin.fixtureCheck.v1",
        "status": "pass",
        "authority": False,
        "authorityClass": "evidence-only",
        "finalCheckName": FINAL_CHECK_NAME,
        "candidateSha": candidate_sha,
        "regression": selftest,
        "hardening": hardening,
        "gate": gate,
        "productionAdmission": False,
        "allRepositoriesEnforced": False,
        "boundary": "Current-head exact-SHA fixture and migration-safety proof only. It cannot satisfy production merge admission before accepted ADRS #233 cutover and readback.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Final-scope purpose join gate adapter.")
    parser.add_argument("command", nargs="?", choices=["selftest", "check"], default="selftest")
    parser.add_argument("--candidate-sha")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "check":
        if not args.candidate_sha:
            parser.error("check requires --candidate-sha")
        report = run_check(args.candidate_sha)
    else:
        report = run_selftest()
    print(canonical(report) if args.json else f"final-scope-purpose-join:{report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
