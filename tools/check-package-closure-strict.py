#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPILER_PATH = ROOT / "tools" / "build-package-responsibility-closure.py"
FIXTURE = ROOT / "fixtures" / "package-responsibility-closure"

NON_BLOCKING = {"generated-artifact-misclassified"}


def load_compiler():
    spec = importlib.util.spec_from_file_location("package_responsibility_closure", COMPILER_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit("package-closure-strict:error:cannot-load-compiler")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def emit(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(emit(row) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def diagnostic_code(row: dict[str, Any]) -> str:
    value = row.get("diagnostic")
    return value if isinstance(value, str) else "unknown"


def is_blocking(row: dict[str, Any]) -> bool:
    if row.get("blocking_level") == "warning":
        return False
    return diagnostic_code(row) not in NON_BLOCKING


def evaluate(result: dict[str, list[dict[str, Any]]], mode: str) -> dict[str, Any]:
    work_orders = result.get("work_orders", [])
    diagnostics = result.get("diagnostics", [])
    blocking = [row for row in work_orders if is_blocking(row)]
    status = "pass" if not blocking else ("fail" if mode == "strict" else "report-generated")
    return {
        "kind": "governance.packageClosureStrictGate.report.v1",
        "status": status,
        "mode": mode,
        "authority": False,
        "blockingDrifts": len(blocking),
        "diagnostics": sorted({diagnostic_code(row) for row in diagnostics}),
        "blockingDiagnostics": sorted({diagnostic_code(row) for row in blocking}),
        "rule": "pass means ADRS/feat package closure has no blocking drift; report generation alone is not pass",
    }


def run_gate(adrs: Path, repo: Path, responses: Path, out_dir: Path | None, mode: str) -> dict[str, Any]:
    compiler = load_compiler()
    result = compiler.compile_all(adrs, repo, responses)
    report = evaluate(result, mode)
    if out_dir is not None:
        compiler.write_outputs(out_dir, result)
        write_json(out_dir / "package-closure-strict-gate.json", report)
    return report


def build_clean_fixture(root: Path) -> tuple[Path, Path, Path]:
    adrs = root / "adrs"
    repo = root / "repo"
    responses = root / "responses"
    write_jsonl(adrs / "package-obligations.jsonl", [
        {
            "kind": "packageObligation.v1",
            "adrs_ref": "adrs-clean",
            "obligation_id": "obl-clean",
            "repo_locator": "repo:repo",
            "package_id": "clean",
            "package_path": "packages/clean",
            "owner_role": "owner",
            "required_tests": ["npm-test"],
            "target_universe": "selected",
        }
    ])
    package_dir = repo / "packages" / "clean"
    write_json(package_dir / "package.json", {"name": "clean", "scripts": {"test": "true"}})
    write_jsonl(responses / "package-responses.jsonl", [
        {
            "kind": "packageResponse.v1",
            "adrs_ref": "adrs-clean",
            "obligation_id": "obl-clean",
            "repo_locator": "repo:repo",
            "package_id": "clean",
            "owner_role": "owner",
            "required_tests": ["npm-test"],
            "receipts": ["receipt-clean"],
            "status": "implemented",
            "authority": False,
        }
    ])
    return adrs, repo, responses


def selftest() -> dict[str, Any]:
    dirty = run_gate(FIXTURE / "adrs", FIXTURE / "repo", FIXTURE / "responses", None, "strict")
    if dirty["status"] != "fail" or dirty["blockingDrifts"] <= 0:
        raise SystemExit(emit({"case": "dirty fixture must fail", "report": dirty}))
    shadow = run_gate(FIXTURE / "adrs", FIXTURE / "repo", FIXTURE / "responses", None, "shadow")
    if shadow["status"] != "report-generated":
        raise SystemExit(emit({"case": "dirty shadow fixture must not be pass", "report": shadow}))
    with tempfile.TemporaryDirectory() as tmp:
        adrs, repo, responses = build_clean_fixture(Path(tmp))
        clean = run_gate(adrs, repo, responses, None, "strict")
    if clean["status"] != "pass" or clean["blockingDrifts"] != 0:
        raise SystemExit(emit({"case": "clean fixture must pass", "report": clean}))
    return {
        "kind": "governance.packageClosureStrictGate.selftest.v1",
        "status": "pass",
        "authority": False,
        "dirtyFixtureStatus": dirty["status"],
        "shadowFixtureStatus": shadow["status"],
        "cleanFixtureStatus": clean["status"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail package closure when blocking drift remains.")
    parser.add_argument("command", nargs="?", choices=["check", "selftest"], default="check")
    parser.add_argument("--adrs", type=Path, default=FIXTURE / "adrs")
    parser.add_argument("--repo", type=Path, default=FIXTURE / "repo")
    parser.add_argument("--responses", type=Path, default=FIXTURE / "responses")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--mode", choices=["strict", "shadow"], default="strict")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.command == "selftest":
        report = selftest()
        print(emit(report) if args.json else "package-closure-strict:selftest-pass")
        return 0

    report = run_gate(args.adrs, args.repo, args.responses, args.out_dir, args.mode)
    print(emit(report) if args.json else f"package-closure-strict:{report['status']}")
    return 1 if args.mode == "strict" and report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
