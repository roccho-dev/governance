from __future__ import annotations

import argparse
import fnmatch
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ast_grep_py import SgRoot

from .common import canonical_json, digest_file, read_jsonl, write_json, write_jsonl


class ScanError(RuntimeError):
    pass


def _module_path(case_dir: Path) -> str:
    go_mod = case_dir / "go.mod"
    if not go_mod.is_file():
        raise ScanError(f"missing go.mod in {case_dir}")
    for raw in go_mod.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("module "):
            value = line.removeprefix("module ").strip()
            if value:
                return value
    raise ScanError(f"missing module directive in {go_mod}")


def _classify_path(relative: str, role_rules: list[dict[str, Any]]) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    normalized = relative.replace(os.sep, "/")
    for row in role_rules:
        prefix = row["payload"]["path_prefix"]
        if normalized.startswith(prefix):
            matches.append((row["subject_key"], row["payload"]["role"]))
    return matches


def _classify_package(relative_package: str, role_rules: list[dict[str, Any]]) -> list[tuple[str, str]]:
    value = relative_package.rstrip("/") + "/"
    return _classify_path(value, role_rules)


def _parse_import_spec(text: str) -> tuple[str | None, str]:
    match = re.fullmatch(r"\s*(?:(\.|_|[A-Za-z_][A-Za-z0-9_]*)\s+)?(?:`([^`]+)`|\"([^\"]+)\")\s*", text)
    if not match:
        raise ScanError(f"cannot parse Go import spec: {text!r}")
    alias = match.group(1)
    path = match.group(2) or match.group(3)
    return alias, path


def _default_alias(import_path: str) -> str:
    return import_path.rstrip("/").split("/")[-1].replace("-", "_")


def _forbidden(call_key: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(call_key, pattern) for pattern in patterns)


def _tidy_findings(case_dir: Path, rule_id: str) -> list[dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="code-gov-tidy-") as tmp:
        copied = Path(tmp) / "module"
        shutil.copytree(case_dir, copied)
        env = os.environ.copy()
        env.update({"GOWORK": "off", "GOPROXY": "off", "GOSUMDB": "off"})
        completed = subprocess.run(
            ["go", "mod", "tidy", "-diff"],
            cwd=copied,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return []
        return [
            {
                "code": "yagni-unused-dependency",
                "rule": rule_id,
                "path": "go.mod",
                "message": "go mod tidy -diff is not clean",
                "evidence": (completed.stdout + completed.stderr).strip(),
            }
        ]


def scan_case(case_dir: Path, rules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    role_rules = [row for row in rules if row["payload"]["rule_type"] == "path-role"]
    dep_rules = {
        row["payload"]["from_role"]: row
        for row in rules
        if row["payload"]["rule_type"] == "dependency-edge"
    }
    effect_rules = [row for row in rules if row["payload"]["rule_type"] == "effect-boundary"]
    yagni_rules = [row for row in rules if row["payload"]["rule_type"] == "yagni-unused-dependency"]

    module = _module_path(case_dir)
    facts: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    nested_modules = {path.parent for path in case_dir.rglob("go.mod") if path.parent != case_dir}

    def in_nested_module(path: Path) -> bool:
        return any(module_dir == path or module_dir in path.parents for module_dir in nested_modules)

    go_files = sorted(
        path
        for path in case_dir.rglob("*.go")
        if "vendor" not in path.parts
        and not path.name.endswith("_test.go")
        and not in_nested_module(path)
    )
    if not go_files:
        findings.append(
            {"code": "no-production-source", "rule": None, "path": ".", "message": "no production Go source"}
        )

    for path in go_files:
        relative = path.relative_to(case_dir).as_posix()
        matches = _classify_path(relative, role_rules)
        if not matches:
            findings.append(
                {
                    "code": "unclassified-file",
                    "rule": None,
                    "path": relative,
                    "message": "production file has no role",
                }
            )
            continue
        if len(matches) != 1:
            findings.append(
                {
                    "code": "multiple-role",
                    "rule": None,
                    "path": relative,
                    "message": f"production file matches multiple roles: {matches}",
                }
            )
            continue
        role_rule, role = matches[0]
        facts.append({"kind": "file-role", "path": relative, "role": role, "rule": role_rule})

        source = path.read_text(encoding="utf-8")
        try:
            root = SgRoot(source, "go").root()
        except BaseException as exc:
            findings.append(
                {
                    "code": "parse-error",
                    "rule": role_rule,
                    "path": relative,
                    "message": f"ast-grep parse failed: {type(exc).__name__}: {exc}",
                }
            )
            continue
        if root.has(kind="ERROR"):
            findings.append(
                {
                    "code": "parse-error",
                    "rule": role_rule,
                    "path": relative,
                    "message": "tree-sitter produced ERROR node",
                }
            )
            continue

        aliases: dict[str, str] = {}
        for node in root.find_all(kind="import_spec"):
            alias, import_path = _parse_import_spec(node.text())
            resolved_alias = alias if alias not in (None, ".", "_") else _default_alias(import_path)
            aliases[resolved_alias] = import_path
            facts.append(
                {
                    "kind": "import",
                    "path": relative,
                    "role": role,
                    "alias": alias,
                    "import_path": import_path,
                }
            )
            if alias == ".":
                findings.append(
                    {
                        "code": "kiss-dot-import",
                        "rule": role_rule,
                        "path": relative,
                        "message": f"dot import is forbidden: {import_path}",
                    }
                )
            if alias == "_" and role not in {"adapter", "composition"}:
                findings.append(
                    {
                        "code": "effect-blank-import",
                        "rule": role_rule,
                        "path": relative,
                        "message": f"blank import outside adapter/composition: {import_path}",
                    }
                )

            if import_path == module or import_path.startswith(module + "/"):
                relative_package = import_path[len(module) :].lstrip("/")
                target_matches = _classify_package(relative_package, role_rules)
                if len(target_matches) != 1:
                    findings.append(
                        {
                            "code": "unclassified-internal-import",
                            "rule": role_rule,
                            "path": relative,
                            "message": f"internal import {import_path} maps to {target_matches}",
                        }
                    )
                else:
                    _, target_role = target_matches[0]
                    facts.append(
                        {
                            "kind": "dependency",
                            "path": relative,
                            "from_role": role,
                            "to_role": target_role,
                            "import_path": import_path,
                        }
                    )
                    dep_rule = dep_rules.get(role)
                    if dep_rule is None or target_role not in dep_rule["payload"]["allowed_to_roles"]:
                        findings.append(
                            {
                                "code": "dependency-edge",
                                "rule": dep_rule["subject_key"] if dep_rule else None,
                                "path": relative,
                                "message": f"forbidden role dependency {role} -> {target_role}: {import_path}",
                            }
                        )

        effect_patterns: list[tuple[str, str]] = []
        for effect_rule in effect_rules:
            if role in effect_rule["payload"]["roles"]:
                effect_patterns.extend((effect_rule["subject_key"], pattern) for pattern in effect_rule["payload"]["forbidden_calls"])

        for call in root.find_all(kind="call_expression"):
            function = call.field("function")
            if function is None or function.kind() != "selector_expression":
                continue
            operand = function.field("operand")
            field = function.field("field")
            if operand is None or field is None or operand.kind() != "identifier":
                continue
            alias = operand.text()
            import_path = aliases.get(alias)
            if import_path is None:
                continue
            call_key = f"{import_path}.{field.text()}"
            facts.append(
                {
                    "kind": "call",
                    "path": relative,
                    "role": role,
                    "call": call_key,
                }
            )
            matched_rules = sorted({rule_id for rule_id, pattern in effect_patterns if _forbidden(call_key, [pattern])})
            if matched_rules:
                findings.append(
                    {
                        "code": "effect-boundary",
                        "rule": matched_rules[0],
                        "path": relative,
                        "message": f"forbidden direct effect call from {role}: {call_key}",
                    }
                )

    for rule in yagni_rules:
        findings.extend(_tidy_findings(case_dir, rule["subject_key"]))

    facts.sort(key=canonical_json)
    findings.sort(key=canonical_json)
    return facts, findings


def run(project_root: Path, projection_jsonl: Path, output_dir: Path) -> dict[str, Any]:
    active_rows = read_jsonl(projection_jsonl)
    rules = [row for row in active_rows if row["semantic_kind"] == "code-rule"]
    cases = [row for row in active_rows if row["semantic_kind"] == "test-case"]

    all_facts: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []

    for case in sorted(cases, key=lambda row: row["subject_key"]):
        case_path = project_root / case["payload"]["path"]
        facts, findings = scan_case(case_path, rules)
        for fact in facts:
            all_facts.append({"case": case["subject_key"], **fact})
        for finding in findings:
            all_findings.append({"case": case["subject_key"], **finding})
        actual_codes = sorted({finding["code"] for finding in findings})
        expected_codes = sorted(case["payload"]["expected_findings"])
        expected = case["payload"]["expected"]
        actual = "pass" if not findings else "fail"
        expectation_met = actual == expected and set(expected_codes).issubset(actual_codes)
        case_results.append(
            {
                "case": case["subject_key"],
                "path": case["payload"]["path"],
                "expected": expected,
                "actual": actual,
                "expected_findings": expected_codes,
                "actual_findings": actual_codes,
                "expectation_met": expectation_met,
            }
        )

    failed_expectations = [result for result in case_results if not result["expectation_met"]]
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "facts.jsonl", sorted(all_facts, key=canonical_json))
    write_jsonl(output_dir / "findings.jsonl", sorted(all_findings, key=canonical_json))
    write_json(output_dir / "case-results.json", {"kind": "code-governance-case-results.v1", "cases": case_results})
    receipt = {
        "kind": "code-governance-scan-receipt.v1",
        "status": "pass" if not failed_expectations else "fail",
        "authority": False,
        "ast_grep_py_version": "0.44.1",
        "go_version": subprocess.run(["go", "version"], text=True, capture_output=True, check=True).stdout.strip(),
        "projection_sha256": digest_file(projection_jsonl),
        "facts_sha256": digest_file(output_dir / "facts.jsonl"),
        "findings_sha256": digest_file(output_dir / "findings.jsonl"),
        "case_results_sha256": digest_file(output_dir / "case-results.json"),
        "case_count": len(case_results),
        "expectation_failure_count": len(failed_expectations),
    }
    write_json(output_dir / "scan-receipt.json", receipt)
    if failed_expectations:
        raise ScanError(f"case expectations failed: {failed_expectations}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--projection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.project_root, args.projection, args.output)
    except ScanError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
