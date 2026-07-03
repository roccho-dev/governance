#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FINAL_CHECK_NAME = "gov-final-scope-purpose-join / gate"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(canonical({"status": "fail", "reason": "cannot-load-module", "path": str(path)}))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_selftest() -> dict[str, Any]:
    closure = load_module("package_closure_strict", ROOT / "tools" / "check-package-closure-strict.py")
    provider = load_module("provider_ci_yaml", ROOT / "tools" / "check-provider-ci-yaml.py")

    closure_report = closure.selftest()
    provider_code = provider.selftest()
    if provider_code != 0:
        raise SystemExit(canonical({"status": "fail", "reason": "provider-ci-selftest-failed", "code": provider_code}))

    if closure_report.get("status") != "pass":
        raise SystemExit(canonical({"status": "fail", "reason": "closure-selftest-failed", "closureReport": closure_report}))

    return {
        "kind": "governance.finalScopePurposeJoin.selftest.v1",
        "status": "pass",
        "authority": False,
        "finalCheckName": FINAL_CHECK_NAME,
        "evidenceMode": "strict-gate-adapter-selftest",
        "consumes": [
            "package closure strict gate",
            "provider CI drift selftest",
            "future README projection drift findings",
            "future govPackageOutput producer provenance findings",
            "future selected-universe admission rows",
        ],
        "strictFailureCapability": [
            "missing package inventory or package path",
            "missing package response",
            "missing receipt",
            "non-active admission",
            "provider CI drift",
            "manual or stale provider CI edit",
            "expired waiver",
            "generated artifact misclassified as pass",
        ],
        "closureStrictGate": closure_report,
        "providerCiSelftest": "pass",
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
