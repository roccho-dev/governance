#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "package-responsibility-closure"
COMPILER = ROOT / "tools" / "build-package-responsibility-closure.py"
STRICT = ROOT / "tools" / "check-package-closure-strict.py"
WARNING_CODES = {"generated-artifact-misclassified"}


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"package-closure-handoff:error:cannot-load:{path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def emit(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(emit(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(emit(row) + "\n" for row in sorted(rows, key=emit)), encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def s(row: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return default


def code(row: dict[str, Any]) -> str:
    return s(row, "diagnostic", default="unknown")


def blocking(row: dict[str, Any]) -> bool:
    return row.get("blocking_level") != "warning" and code(row) not in WARNING_CODES


def owner_for(c: str) -> str:
    if c in {"package-id-missing", "package-path-missing", "target-universe-unknown"}:
        return "adrs-owner"
    if c == "generated-artifact-misclassified":
        return "governance-scanner-owner"
    if c in {"package-path-drift", "registered-package-missing-on-disk"}:
        return "adrs-owner-and-target-repo-owner"
    if c == "owner-role-mismatch":
        return "declared-owner-role"
    return "target-repo-owner"


def proof_for(c: str) -> list[str]:
    return {
        "unregistered-package": ["ADRS obligation row or explicit source-package exclusion"],
        "claim-missing": ["packageResponse.v1 bound to obligation"],
        "required-test-missing": ["required test exists and is cited"],
        "receipt-missing": ["closure receipt row"],
        "residual-hidden": ["returned residual row"],
        "authority-collision": ["non-authority response"],
        "package-path-drift": ["move receipt or ADRS path update"],
        "registered-package-missing-on-disk": ["package path exists or ADRS path receipt"],
    }.get(c, ["owner review proof and receipt or residual"])


def next_action(c: str) -> str:
    return {
        "unregistered-package": "add ADRS obligation or exclude non-source package",
        "claim-missing": "emit packageResponse.v1",
        "required-test-missing": "add or cite required test",
        "receipt-missing": "attach closure receipt",
        "residual-hidden": "return residual row",
        "authority-collision": "remove authority claim",
    }.get(c, "close package responsibility gap for this diagnostic")


def build_rows(result: dict[str, Any], strict_report: dict[str, Any]) -> dict[str, Any]:
    work_orders = list(result.get("work_orders", []))
    blocking_rows = [row for row in work_orders if blocking(row)]
    routes: list[dict[str, Any]] = []
    proofs: list[dict[str, Any]] = []
    residuals: list[dict[str, Any]] = []
    for row in work_orders:
        c = code(row)
        repo = s(row, "repo_locator", "repoLocator", default="repo:unknown")
        pkg = s(row, "package_id", "packageId", default="unknown")
        gap = s(row, "primary_gap_id", default=f"package-closure:{repo}:{pkg}:{c}")
        base = {"primary_gap_id": gap, "diagnostic": c, "repo_locator": repo, "package_id": pkg, "authority": False}
        route = {**base, "kind": "governance.packageClosureOwnerRoute.v1", "owner_role": owner_for(c), "next_action": next_action(c), "blocking": blocking(row)}
        route["digest"] = digest(route)
        routes.append(route)
        proof = {**base, "kind": "governance.packageClosureRequiredProof.v1", "required_proofs": proof_for(c), "receipt_required": True, "residual_required_when_unclosed": True}
        proof["digest"] = digest(proof)
        proofs.append(proof)
        if blocking(row):
            residual = {**base, "kind": "governance.packageClosureResidual.v1", "status": "returned", "residual_policy": "return receipt when closed or residual when still blocked"}
            residual["digest"] = digest(residual)
            residuals.append(residual)
    status = "closure-pass" if strict_report.get("status") == "pass" else "handoff-ready"
    summary = {
        "kind": "governance.packageClosureHandoff.summary.v1",
        "status": status,
        "authority": False,
        "strict_status": strict_report.get("status"),
        "counts": {"work_orders": len(work_orders), "blocking_work_orders": len(blocking_rows), "owner_routes": len(routes), "required_proofs": len(proofs), "returned_residuals": len(residuals)},
        "rule": "closure-pass requires zero blocking drift; handoff-ready means every blocking drift has owner, proof, next action, and residual",
    }
    summary["digest"] = digest(summary)
    return {"summary": summary, "work_orders": work_orders, "routes": routes, "proofs": proofs, "residuals": residuals}


def readme(summary: dict[str, Any]) -> str:
    c = summary["counts"]
    return f"""# Package closure handoff

This packet is non-authority. ADRS remains the meaning authority.

Status: `{summary['status']}`

| item | count |
|---|---:|
| work orders | {c['work_orders']} |
| blocking work orders | {c['blocking_work_orders']} |
| owner routes | {c['owner_routes']} |
| required proof rows | {c['required_proofs']} |
| returned residual rows | {c['returned_residuals']} |

`closure-pass` means zero blocking drift.
`handoff-ready` means every blocking drift has owner, proof, next action, and residual.
"""


def write_packet(out: Path, rows: dict[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "package-closure-handoff.json", rows["summary"])
    write_jsonl(out / "package-work-orders.jsonl", rows["work_orders"])
    write_jsonl(out / "package-owner-routing.jsonl", rows["routes"])
    write_jsonl(out / "package-required-proofs.jsonl", rows["proofs"])
    write_jsonl(out / "package-residuals.jsonl", rows["residuals"])
    (out / "README.handoff.md").write_text(readme(rows["summary"]), encoding="utf-8")
    files = ["package-closure-handoff.json", "package-work-orders.jsonl", "package-owner-routing.jsonl", "package-required-proofs.jsonl", "package-residuals.jsonl", "README.handoff.md"]
    manifest = {"kind": "governance.packageClosureHandoff.manifest.v1", "authority": False, "required_files": files, "files": [{"path": f, "sha256": sha(out / f)} for f in files]}
    manifest["digest"] = digest(manifest)
    write_json(out / "handoff-manifest.json", manifest)


def build(adrs: Path, repo: Path, responses: Path, out: Path | None) -> dict[str, Any]:
    compiler = load(COMPILER, "pkg_closure_compiler")
    strict = load(STRICT, "pkg_closure_strict")
    result = compiler.compile_all(adrs, repo, responses)
    rows = build_rows(result, strict.evaluate(result, "strict"))
    if out is not None:
        write_packet(out, rows)
    return rows["summary"]


def selftest() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "handoff"
        summary = build(FIXTURE / "adrs", FIXTURE / "repo", FIXTURE / "responses", out)
        counts = summary["counts"]
        if summary["status"] != "handoff-ready" or counts["blocking_work_orders"] <= 0:
            raise SystemExit(emit({"case": "dirty fixture must be handoff-ready", "summary": summary}))
        if counts["owner_routes"] != counts["work_orders"] or counts["required_proofs"] != counts["work_orders"]:
            raise SystemExit(emit({"case": "every work order needs route and proof", "summary": summary}))
        if counts["returned_residuals"] != counts["blocking_work_orders"]:
            raise SystemExit(emit({"case": "every blocking work order needs residual", "summary": summary}))
        manifest = json.loads((out / "handoff-manifest.json").read_text(encoding="utf-8"))
        for rel in manifest["required_files"]:
            if not (out / rel).exists() or (out / rel).stat().st_size == 0:
                raise SystemExit(emit({"case": "required file missing", "path": rel}))
        a = (out / "handoff-manifest.json").read_text(encoding="utf-8")
        again = build(FIXTURE / "adrs", FIXTURE / "repo", FIXTURE / "responses", out)
        b = (out / "handoff-manifest.json").read_text(encoding="utf-8")
        if a != b or summary != again:
            raise SystemExit("handoff output must be deterministic")
    return {"kind": "governance.packageClosureHandoff.selftest.v1", "status": "pass", "authority": False, "dirtyFixtureStatus": "handoff-ready"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", nargs="?", choices=["build", "selftest"], default="build")
    p.add_argument("--adrs", type=Path, default=FIXTURE / "adrs")
    p.add_argument("--repo", type=Path, default=FIXTURE / "repo")
    p.add_argument("--responses", type=Path, default=FIXTURE / "responses")
    p.add_argument("--out-dir", type=Path)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    if args.command == "selftest":
        report = selftest()
        print(emit(report) if args.json else "package-closure-handoff:selftest-pass")
        return 0
    summary = build(args.adrs, args.repo, args.responses, args.out_dir)
    print(emit(summary) if args.json else f"package-closure-handoff:{summary['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
