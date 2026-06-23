#!/usr/bin/env python3
"""Executable proof for repo-governance core+port and CLI adapter."""

from __future__ import annotations

import argparse
import ast
import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LIB_SRC = ROOT / "packages/repo-governance/src"
CLI_SRC = ROOT / "packages/repo-governance-cli/src"
sys.path.insert(0, str(LIB_SRC))

from repo_governance import REQUIRED_RULES, evaluate  # noqa: E402

RULES = [
    "repo-is-packages",
    "core-port-is-lib",
    "adapter-placement",
    "dependency-direction",
    "goal-no-goal",
    "generated-non-authority",
    "readme-contract",
    "waiver-expiry",
    "hidden-input-ban",
]


def adr_bundle(extra_rule: str | None = None) -> dict[str, Any]:
    rules = [{"ruleId": rule, "adrRef": "roccho-dev/adrs#21", "status": "accepted"} for rule in RULES]
    if extra_rule:
        rules.append({"ruleId": extra_rule, "adrRef": "roccho-dev/adrs#21", "status": "accepted"})
    return {
        "kind": "governance.adrBundle.v1",
        "bundleId": "adrs-main-repo-governance-v1",
        "status": "accepted",
        "sourceRef": "roccho-dev/adrs#21",
        "rules": rules,
    }


def valid_repo() -> dict[str, Any]:
    return {
        "kind": "governance.repoSnapshot.v1",
        "repoId": "roccho-dev/governance",
        "evaluationDate": "2026-06-23",
        "goal": "Project and enforce accepted cross-repo governance decisions without owning authority.",
        "noGoals": ["No runtime business operations.", "No independent decision authority."],
        "generated": {"authority": False},
        "readme": {"authority": False, "contractSource": "repo-governance", "generatedBlock": True},
        "hiddenInputs": [],
        "packages": [
            {
                "packageId": "repo-governance",
                "classification": "lib",
                "shape": "core+port",
                "goal": "Return deterministic repo contracts, violations, explanations, docs, and plans from explicit inputs.",
                "noGoals": ["No file, console, network, clock, environment, or remote mutation effects."],
                "dependencies": [],
                "capabilities": [],
                "definesRules": False,
            },
            {
                "packageId": "repo-governance-cli",
                "classification": "adapter-package",
                "shape": "adapter",
                "adapterKind": "cli",
                "goal": "Expose repo-governance through explicit file input, console output, output files, and process status.",
                "noGoals": ["No rule semantics or business judgement."],
                "dependencies": ["repo-governance"],
                "capabilities": ["exit-code", "filesystem-read", "filesystem-write", "stderr", "stdout"],
                "definesRules": False,
            },
        ],
        "surfaces": [
            {
                "surfaceId": "e2e/repo-governance",
                "classification": "e2e",
                "shape": "adapter",
                "adapterKind": "fixture-runner",
                "goal": "Prove accepted behavior and destructive cases.",
                "noGoals": ["No reusable runtime package and no authority."],
                "authority": False,
            },
            {
                "surfaceId": "example/repo-governance",
                "classification": "example",
                "shape": "adapter",
                "adapterKind": "example",
                "goal": "Explain the smallest valid input and output flow.",
                "noGoals": ["No gate and no authority."],
                "authority": False,
            },
        ],
        "waivers": [],
    }


def rules(result: dict[str, Any]) -> set[str]:
    return {item["ruleId"] for item in result["violations"]}


def source_checks() -> list[str]:
    checks: list[str] = []
    core_tree = ast.parse((LIB_SRC / "repo_governance/core.py").read_text(encoding="utf-8"))
    cli_tree = ast.parse((CLI_SRC / "repo_governance_cli/__main__.py").read_text(encoding="utf-8"))
    banned_imports = {"os", "pathlib", "random", "requests", "socket", "subprocess", "sys", "time", "urllib"}
    imports: set[str] = set()
    for node in ast.walk(core_tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    assert not (imports & banned_imports), sorted(imports & banned_imports)
    checks.append("core-forbidden-imports:PASS")

    banned_calls = {"open", "print", "getenv", "now", "today", "time"}
    calls: set[str] = set()
    for node in ast.walk(core_tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    assert not (calls & banned_calls), sorted(calls & banned_calls)
    checks.append("core-forbidden-calls:PASS")

    fn_names = {node.name for node in ast.walk(cli_tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert not sorted(name for name in fn_names if name.startswith(("check_", "project_", "evaluate_", "rule_")))
    checks.append("cli-no-rule-functions:PASS")

    strings = {node.value for node in ast.walk(cli_tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert not (set(REQUIRED_RULES) & strings)
    checks.append("cli-no-rule-id-literals:PASS")
    return checks


def destructive_cases() -> list[tuple[str, list[str], Any]]:
    return [
        ("invalid-adapter-in-core", ["hidden-input-ban"], lambda s: s["packages"][0]["capabilities"].append("network")),
        ("invalid-generated-authority", ["generated-non-authority"], lambda s: s["generated"].__setitem__("authority", True)),
        ("invalid-cli-defines-rules", ["adapter-placement"], lambda s: s["packages"][1].__setitem__("definesRules", True)),
        ("invalid-lib-depends-adapter", ["dependency-direction"], lambda s: s["packages"][0]["dependencies"].append("repo-governance-cli")),
        ("invalid-missing-goal", ["goal-no-goal"], lambda s: s["packages"][0].__setitem__("goal", "")),
        ("invalid-readme-authority", ["readme-contract"], lambda s: s["readme"].__setitem__("authority", True)),
        ("invalid-expired-waiver", ["waiver-expiry"], lambda s: s["waivers"].append({"ruleId": "hidden-input-ban", "subject": "repo-governance", "expiresOn": "2026-01-01", "adrRef": "roccho-dev/adrs#21"})),
        ("invalid-hidden-input", ["hidden-input-ban"], lambda s: s["hiddenInputs"].append("current-time")),
    ]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_cli(bundle: dict[str, Any], snapshot: dict[str, Any], expected_rc: int) -> tuple[dict[str, Any], list[str]]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(LIB_SRC), str(CLI_SRC)))
    with tempfile.TemporaryDirectory(prefix="repo-governance-proof-") as temp:
        root = Path(temp)
        bundle_path = root / "adr-bundle.json"
        snapshot_path = root / "repo-snapshot.json"
        out_dir = root / "out"
        write_json(bundle_path, bundle)
        write_json(snapshot_path, snapshot)
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "repo_governance_cli",
                "--adr-bundle",
                str(bundle_path),
                "--repo-snapshot",
                str(snapshot_path),
                "--out-dir",
                str(out_dir),
                "--output",
                "json",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == expected_rc, (completed.returncode, completed.stdout, completed.stderr)
        names = sorted(path.name for path in out_dir.iterdir())
        assert names == [
            "package.contracts.json",
            "plan.json",
            "provenance.json",
            "readme.generated.md",
            "repo.contract.json",
            "violations.json",
        ], names
        return json.loads(completed.stdout), names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt")
    args = parser.parse_args()
    checks: list[str] = []
    bundle = adr_bundle()
    valid = valid_repo()
    valid_result = evaluate(bundle, valid).to_dict()
    assert valid_result["passed"] is True, valid_result["violations"]
    checks.append("valid-repo:PASS")

    shuffled = copy.deepcopy(valid)
    shuffled["packages"].reverse()
    shuffled["surfaces"].reverse()
    shuffled["noGoals"].reverse()
    for package in shuffled["packages"]:
        package["noGoals"].reverse()
        package["capabilities"].reverse()
        package["dependencies"].reverse()
    assert evaluate(bundle, shuffled).to_dict()["resultDigest"] == valid_result["resultDigest"]
    checks.append("input-order-invariant:PASS")

    negatives: list[dict[str, Any]] = []
    for name, expected, mutate in destructive_cases():
        snapshot = valid_repo()
        mutate(snapshot)
        result = evaluate(bundle, snapshot).to_dict()
        assert result["passed"] is False, name
        assert set(expected) <= rules(result), (name, expected, result["violations"])
        checks.append(f"{name}:REJECTED")
        negatives.append({"case": name, "expectedRuleIds": expected, "actualRuleIds": sorted(rules(result)), "resultDigest": result["resultDigest"]})

    unknown = evaluate(adr_bundle("invented-rule"), valid).to_dict()
    assert unknown["passed"] is False
    assert "bundle-contract" in rules(unknown)
    assert any(item["code"] == "RULE_UNKNOWN" for item in unknown["violations"])
    checks.append("unknown-rule:REJECTED")
    checks.extend(source_checks())

    cli_valid, outputs = run_cli(bundle, valid, 0)
    assert cli_valid["resultDigest"] == valid_result["resultDigest"]
    checks.append("cli-valid-exit-0:PASS")
    assert run_cli(bundle, valid, 0)[0] == cli_valid
    checks.append("cli-clean-room-repeat:PASS")
    invalid = valid_repo()
    invalid["packages"][0]["capabilities"].append("network")
    assert run_cli(bundle, invalid, 1)[0]["passed"] is False
    checks.append("cli-invalid-exit-1:PASS")

    receipt = {
        "kind": "governance.repoGovernanceProofReceipt.v1",
        "authority": False,
        "sourceDecision": "roccho-dev/adrs#21",
        "projectorVersion": valid_result["provenance"]["projectorVersion"],
        "validResultDigest": valid_result["resultDigest"],
        "checkCount": len(checks),
        "checks": checks,
        "negativeCases": negatives,
        "cliOutputFiles": outputs,
        "verdict": "PASS",
    }
    text = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    print(text, end="")
    if args.receipt:
        Path(args.receipt).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
