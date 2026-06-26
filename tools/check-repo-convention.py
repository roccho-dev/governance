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


def check_ci(repo_root: Path, ci_path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    actual = workflow_files(repo_root)
    if not ci_path.exists():
        return [finding("ci-intent-missing", "ci intent file is missing", path=str(ci_path))]
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
