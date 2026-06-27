#!/usr/bin/env python3
"""Stable Nix-facing claim admission checker.

This wrapper keeps the exported CLI surface stable while the internal compiler can
remain small. It is a deterministic non-authority checker: ADRS records grant,
governance joins and reports.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / "tools" / "compile-claim-port-joins.py"
ACTIVE = "organization-active"


def canonical(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        raise SystemExit(f"missing input: {path}")
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


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")


def run_compile(
    grants: Path,
    assertions: Path,
    receipts: Path,
    out: Path,
    official_view: Path | None,
    require_active: bool,
) -> int:
    cmd = [
        sys.executable,
        str(COMPILER),
        "compile",
        "--grants",
        str(grants),
        "--assertions",
        str(assertions),
        "--receipts",
        str(receipts),
        "--out",
        str(out),
    ]
    if require_active:
        cmd.append("--require-active")
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.returncode != 0:
        return result.returncode
    if official_view is not None:
        admissions = read_jsonl(out)
        active_rows = []
        for row in admissions:
            if row.get("admissionResult") == ACTIVE:
                active = dict(row)
                active["kind"] = "governance.organizationOfficialView.v1"
                active_rows.append(active)
        write_jsonl(official_view, active_rows)
    return 0


def selftest() -> int:
    compiler = subprocess.run([sys.executable, str(COMPILER), "selftest"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if compiler.stdout:
        sys.stdout.write(compiler.stdout)
    if compiler.stderr:
        sys.stderr.write(compiler.stderr)
    if compiler.returncode != 0:
        return compiler.returncode

    with tempfile.TemporaryDirectory(prefix="claim-admission-check-") as raw:
        root = Path(raw)
        grants = root / "upstream-grants.jsonl"
        assertions = root / "downstream-assertions.jsonl"
        receipts = root / "receipts.jsonl"
        admissions = root / "admissions.jsonl"
        official_view = root / "official-view.jsonl"
        write_jsonl(grants, [
            {
                "kind": "governance.claimPort.upstreamGrant.v1",
                "subjectId": "repo:ops",
                "grantId": "grant:ops-claim-admission",
                "acceptedBundleDigest": "sha256:bundle",
                "sourceClosureDigest": "sha256:closure",
                "lifecycle": "active",
            }
        ])
        write_jsonl(assertions, [
            {
                "kind": "governance.claimPort.downstreamAssertion.v1",
                "subjectId": "repo:ops",
                "assertionId": "assert:ops-claim-admission",
                "acceptedBundleDigest": "sha256:bundle",
                "sourceClosureDigest": "sha256:closure",
                "lifecycle": "active",
            }
        ])
        write_jsonl(receipts, [
            {
                "kind": "governance.claimPort.receipt.v1",
                "subjectId": "repo:ops",
                "receiptId": "receipt:ops-ci",
                "acceptedBundleDigest": "sha256:bundle",
                "sourceClosureDigest": "sha256:closure",
            }
        ])
        code = run_compile(grants, assertions, receipts, admissions, official_view, require_active=True)
        if code != 0:
            return code
        admission_rows = read_jsonl(admissions)
        view_rows = read_jsonl(official_view)
        if len(admission_rows) != 1 or admission_rows[0].get("kind") != "governance.organizationAdmission.v1":
            raise SystemExit("admission output kind missing")
        if admission_rows[0].get("diagnosticClass") != ACTIVE:
            raise SystemExit("admission diagnosticClass missing")
        if len(view_rows) != 1 or view_rows[0].get("kind") != "governance.organizationOfficialView.v1":
            raise SystemExit("official view output missing")
    print(json.dumps({"kind": "governance.claimAdmissionCheck.selftest.v1", "status": "pass"}, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["compile", "selftest"], default="compile")
    parser.add_argument("--upstream-grants", "--grants", dest="grants", type=Path)
    parser.add_argument("--downstream-assertions", "--assertions", dest="assertions", type=Path)
    parser.add_argument("--receipts", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--official-view", type=Path)
    parser.add_argument("--require-active", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "selftest":
        return selftest()
    required = [args.grants, args.assertions, args.receipts, args.out]
    if any(value is None for value in required):
        parser.error("compile requires --upstream-grants, --downstream-assertions, --receipts, and --out")
    return run_compile(args.grants, args.assertions, args.receipts, args.out, args.official_view, args.require_active)


if __name__ == "__main__":
    raise SystemExit(main())
