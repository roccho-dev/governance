#!/usr/bin/env python3
"""Aggregate repo convention checks for README and provider CI adapters."""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

README_CHECK_PATH = Path(__file__).with_name("check-readme-artifact.py")
README_CHECK_SPEC = importlib.util.spec_from_file_location("check_readme_artifact", README_CHECK_PATH)
if README_CHECK_SPEC is None or README_CHECK_SPEC.loader is None:
    raise RuntimeError(f"cannot load README check helper: {README_CHECK_PATH}")
README_CHECK_MODULE = importlib.util.module_from_spec(README_CHECK_SPEC)
README_CHECK_SPEC.loader.exec_module(README_CHECK_MODULE)
check_readme = README_CHECK_MODULE.check_readme

VALID_SEVERITIES = {"report_only", "warning", "blocking"}
VALID_README_MODES = {"checked_handwritten", "managed_block", "generated"}
VALID_GOVERNANCE_MODES = {"flake_lib", "flake_false_path", "shadow_unconnected"}
VALID_REPO_CLASSES = {"normal", "root_authority", "bootstrap"}
VALID_ROLES = {"primary_nix_check", "manual_dispatch_alias", "artifact_exporter", "bootstrap_exception"}
WORKFLOW_RE = re.compile(r"^\.github/workflows/.+\.ya?ml$")
BRANCH_INTENT_PATH = "ci.branch-intent.v1.jsonl"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
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


def finding(code: str, message: str, **extra: Any) -> dict[str, Any]:
    row = {"code": code, "message": message}
    row.update(extra)
    return row


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    required = [
        "kind",
        "repo",
        "repo_class",
        "severity",
        "readme_mode",
        "governance_mode",
        "governance_ref",
        "ci_intent_path",
        "readme_path",
    ]
    for key in required:
        if key not in manifest:
            findings.append(finding("manifest-field-missing", f"missing {key}", field=key))
    if manifest.get("kind") != "repo-convention.intent.v1":
        findings.append(finding("manifest-kind-invalid", "kind must be repo-convention.intent.v1"))
    if manifest.get("repo_class") not in VALID_REPO_CLASSES:
        findings.append(finding("repo-class-invalid", "repo_class is invalid", value=manifest.get("repo_class")))
    if manifest.get("severity") not in VALID_SEVERITIES:
        findings.append(finding("severity-invalid", "severity is invalid", value=manifest.get("severity")))
    if manifest.get("readme_mode") not in VALID_README_MODES:
        findings.append(finding("readme-mode-invalid", "readme_mode is invalid", value=manifest.get("readme_mode")))
    if manifest.get("governance_mode") not in VALID_GOVERNANCE_MODES:
        findings.append(finding("governance-mode-invalid", "governance_mode is invalid", value=manifest.get("governance_mode")))
    ref = manifest.get("governance_ref", {})
    if not isinstance(ref, dict) or ref.get("kind") not in {"commit", "digest", "branch", "path", "missing"} or not ref.get("value"):
        findings.append(finding("governance-ref-invalid", "governance_ref must declare kind and value"))
    if manifest.get("repo_class") == "root_authority" and manifest.get("severity") == "blocking":
        findings.append(finding("root-authority-blocking", "root_authority repos must start as report_only or warning"))
    return findings


def workflow_files(repo_root: Path) -> set[str]:
    base = repo_root / ".github" / "workflows"
    if not base.exists():
        return set()
    return {
        path.relative_to(repo_root).as_posix()
        for path in base.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    }


def yaml_list_scalar(value: str) -> list[str] | None:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return None
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]


def workflow_push_branches(workflow_text: str) -> list[str] | None:
    lines = workflow_text.splitlines()
    in_push = False
    push_indent = -1
    in_branches = False
    branch_indent = -1
    branches: list[str] = []
    for raw in lines:
        stripped_line = raw.split("#", 1)[0].rstrip()
        if not stripped_line.strip():
            continue
        indent = len(stripped_line) - len(stripped_line.lstrip(" "))
        text = stripped_line.strip()
        if text == "push:" or text.startswith("push: "):
            in_push = True
            push_indent = indent
            in_branches = False
            inline = text[5:].strip()
            if inline:
                return []
            continue
        if not in_push:
            continue
        if indent <= push_indent and not text.startswith("-"):
            break
        if text.startswith("branches:"):
            inline = text[len("branches:"):].strip()
            parsed = yaml_list_scalar(inline)
            if parsed is not None:
                return parsed
            in_branches = True
            branch_indent = indent
            continue
        if in_branches:
            if indent <= branch_indent and not text.startswith("-"):
                break
            if text.startswith("- "):
                branches.append(text[2:].strip().strip("'\""))
    if in_push:
        return branches
    return None


def load_branch_intents(repo_root: Path, findings: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    path = repo_root / BRANCH_INTENT_PATH
    if not path.exists():
        return {}
    rows = read_jsonl(path)
    result: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(rows, 1):
        workflow_path = row.get("path")
        if row.get("kind") != "ci.branchIntent.v1":
            findings.append(finding("branch-intent-kind-invalid", "branch intent row kind is invalid", row=idx))
        if not isinstance(workflow_path, str) or not WORKFLOW_RE.fullmatch(workflow_path):
            findings.append(finding("branch-intent-path-invalid", "branch intent workflow path is invalid", row=idx, path=workflow_path))
            continue
        expected = row.get("pushBranches")
        if expected is not None and (not isinstance(expected, list) or not all(isinstance(item, str) and item for item in expected)):
            findings.append(finding("branch-intent-push-branches-invalid", "pushBranches must be non-empty strings", path=workflow_path))
        active = row.get("activeBranch")
        if active is not None and (not isinstance(active, str) or not active):
            findings.append(finding("branch-intent-active-branch-invalid", "activeBranch must be a non-empty string", path=workflow_path))
        result[workflow_path] = row
    return result


def check_branch_intent(repo_root: Path, workflow_path: str, row: dict[str, Any]) -> list[dict[str, Any]]:
    expected = row.get("pushBranches")
    if expected is None and isinstance(row.get("activeBranch"), str):
        expected = [row["activeBranch"]]
    if expected is None:
        return []
    workflow_file = repo_root / workflow_path
    if not workflow_file.exists():
        return [finding("branch-intent-workflow-missing", "workflow file for branch intent is missing", path=workflow_path)]
    actual = workflow_push_branches(workflow_file.read_text(encoding="utf-8"))
    if actual is None:
        return [finding("branch-intent-push-missing", "workflow has no push trigger", path=workflow_path)]
    if sorted(actual) != sorted(expected):
        return [finding("branch-intent-mismatch", "workflow push branches do not match declared intent", path=workflow_path, expected=expected, actual=actual)]
    return []


def check_ci(repo_root: Path, ci_path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    actual = workflow_files(repo_root)
    if not ci_path.exists():
        return [finding("ci-intent-missing", "ci intent file is missing", path=str(ci_path))]
    branch_intents = load_branch_intents(repo_root, findings)
    rows = read_jsonl(ci_path)
    declared: dict[str, dict[str, Any]] = {}
    primary_count = 0
    for idx, row in enumerate(rows, 1):
        path = row.get("path")
        if row.get("kind") != "ci.intent.v1":
            findings.append(finding("ci-kind-invalid", "ci intent row kind is invalid", row=idx))
        if not isinstance(path, str) or not WORKFLOW_RE.fullmatch(path):
            findings.append(finding("ci-path-invalid", "workflow path is invalid", row=idx, path=path))
            continue
        declared[path] = row
        role = row.get("role")
        if role not in VALID_ROLES:
            findings.append(finding("ci-role-invalid", "workflow role is invalid", row=idx, path=path, role=role))
        if row.get("authority") is not False:
            findings.append(finding("workflow-authority-invalid", "workflow authority must be false", row=idx, path=path))
        if role == "primary_nix_check":
            primary_count += 1
            workflow_text = (repo_root / path).read_text(encoding="utf-8") if (repo_root / path).exists() else ""
            if "nix flake check" not in workflow_text:
                findings.append(finding("nix-entrypoint-missing", "primary_nix_check must run nix flake check", path=path))
        if path in branch_intents:
            findings.extend(check_branch_intent(repo_root, path, branch_intents[path]))
        if role == "artifact_exporter" and row.get("source") not in {None, "nix-output"}:
            findings.append(finding("artifact-exporter-source-invalid", "artifact_exporter source must be nix-output", path=path))
        if role == "bootstrap_exception":
            exc = row.get("exception")
            if not isinstance(exc, dict):
                findings.append(finding("exception-missing", "bootstrap_exception requires exception object", path=path))
            else:
                for key in ["owner", "reason", "expiry"]:
                    if not exc.get(key):
                        findings.append(finding("exception-field-missing", f"exception requires {key}", path=path, field=key))
                if exc.get("expiry"):
                    try:
                        if date.fromisoformat(exc["expiry"]) < date.today():
                            findings.append(finding("exception-expired", "bootstrap_exception expiry is in the past", path=path))
                    except ValueError:
                        findings.append(finding("exception-expiry-invalid", "expiry must be ISO date", path=path))
    for path in sorted(set(branch_intents) - set(declared)):
        findings.append(finding("branch-intent-undeclared-workflow", "branch intent references an undeclared workflow", path=path))
    if actual and primary_count == 0:
        findings.append(finding("primary-nix-check-missing", "one primary_nix_check workflow is required"))
    declared_paths = set(declared)
    for path in sorted(actual - declared_paths):
        findings.append(finding("undeclared-workflow", "workflow file is not declared", path=path))
    for path in sorted(declared_paths - actual):
        findings.append(finding("declared-workflow-missing", "declared workflow file is missing", path=path))
    return findings


def check_readme_govlib_contract(repo_root: Path) -> list[dict[str, Any]]:
    script = repo_root / "tools" / "check-readme-govlib-contract.py"
    if not script.exists():
        return [finding("readme-govlib-contract-missing", "README gov-lib contract check is missing", path=str(script))]
    result = subprocess.run([sys.executable, str(script)], cwd=repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode == 0:
        return []
    return [finding("readme-govlib-contract-failed", "README gov-lib contract check failed", stdout=result.stdout, stderr=result.stderr)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else repo_root / args.manifest
    manifest = read_json(manifest_path)
    findings = validate_manifest(manifest)
    readme_path = repo_root / manifest.get("readme_path", "README.md")
    ci_path = repo_root / manifest.get("ci_intent_path", "ci.intent.v1.jsonl")
    findings.extend(check_readme(readme_path, manifest.get("readme_mode", "")))
    findings.extend(check_ci(repo_root, ci_path))
    findings.extend(check_readme_govlib_contract(repo_root))
    severity = manifest.get("severity", "blocking")
    status = "pass" if not findings else "fail" if severity == "blocking" else "warn"
    report = {
        "kind": "governance.repoConventionCheck.v1",
        "repo": manifest.get("repo"),
        "severity": severity,
        "status": status,
        "findings": findings,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
