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


def run_selftest() -> dict[str, Any]:
    components = [
        run_component("package-closure-strict", [sys.executable, "tools/check-package-closure-strict.py", "selftest", "--json"]),
        run_component("required-repo-org-join", [sys.executable, "tools/check-package-required-repo-org-join.py", "selftest"]),
        run_component("provider-ci-yaml", [sys.executable, "tools/check-provider-ci-yaml.py", "selftest"]),
        run_component("merge-write-boundary-final-gate", [sys.executable, "tools/check-merge-write-boundary-final-gate.py", "selftest", "--json"]),
    ]
    failed = [row for row in components if row["status"] != "pass"]
    if failed:
        raise SystemExit(canonical({"kind": "governance.finalScopePurposeJoin.selftest.v1", "status": "fail", "failedComponents": failed}))

    return {
        "kind": "governance.finalScopePurposeJoin.selftest.v1",
        "status": "pass",
        "authority": False,
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
        ],
        "boundary": "This is the final gate adapter and regression surface. It is not branch-protection cutover, not ADRS authority, and not proof that all downstream selected repos are active.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Final-scope purpose join gate adapter.")
    parser.add_argument("command", nargs="?", choices=["selftest", "check"], default="selftest")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = run_selftest()
    print(canonical(report) if args.json else f"final-scope-purpose-join:{report['status']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
