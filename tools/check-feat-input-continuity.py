#!/usr/bin/env python3
"""Check that feat-input projection remains usable after governance cutover.

This is a projection/continuity check only. It does not make governance an
authority owner, and it does not resolve sourceAuthority to an active owner.
Missing authority-owner rows remain a separate cutover blocker.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile


ROOT_REL_SPEC = pathlib.Path("records/specs")
LAYOUT_REL_SPEC = pathlib.Path("governance-records-main/records/specs")


def read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: pathlib.Path):
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"{path}:{lineno}: invalid json: {exc}") from exc


def package_contracts(path: pathlib.Path) -> dict[str, dict]:
    rows = {}
    for row in read_jsonl(path):
        package_id = row.get("packageId")
        if not package_id:
            raise SystemExit(f"{path}: package-contract row without packageId")
        if package_id in rows:
            raise SystemExit(f"{path}: duplicate packageId {package_id}")
        rows[package_id] = row
    return rows


def stage_tool_layout(root: pathlib.Path) -> pathlib.Path:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="feat-input-continuity-"))
    dst = tmp / LAYOUT_REL_SPEC
    dst.mkdir(parents=True)
    for name in ["package-contract.v1.jsonl", "dependency-edge.v1.jsonl"]:
        shutil.copy2(root / ROOT_REL_SPEC / name, dst / name)
    return tmp


def run_make_feat_input(root: pathlib.Path, staged_root: pathlib.Path, package_id: str) -> str:
    out = staged_root / f"{package_id}.fresh.json"
    cmd = [
        sys.executable,
        str(root / "tools/make-feat-input.py"),
        str(staged_root),
        package_id,
        "--out",
        str(out),
    ]
    completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        raise SystemExit(
            f"make-feat-input failed for {package_id}: rc={completed.returncode}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return out.read_text(encoding="utf-8")


def diff_text(label: str, expected: str, actual: str) -> None:
    if expected == actual:
        return
    import difflib

    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(True),
            actual.splitlines(True),
            fromfile=f"{label}:committed",
            tofile=f"{label}:fresh",
        )
    )
    raise SystemExit(f"{label}: stale feat-input projection\n{diff}")


def check_committed_projection(root: pathlib.Path, staged_root: pathlib.Path) -> list[str]:
    generated = root / "generated/feat-inputs"
    paths = sorted(generated.glob("*.json"))
    if not paths:
        raise SystemExit("generated/feat-inputs contains no feat-input JSON files")
    checked = []
    for path in paths:
        package_id = path.stem
        committed = path.read_text(encoding="utf-8")
        fresh = run_make_feat_input(root, staged_root, package_id)
        diff_text(package_id, committed, fresh)
        checked.append(package_id)
    return checked


def check_projection_digest(root: pathlib.Path, committed_packages: list[str]) -> None:
    ledger_path = root / ROOT_REL_SPEC / "projection-digest.v1.jsonl"
    ledger = {row["packageId"]: row for row in read_jsonl(ledger_path)}
    missing = sorted(set(committed_packages) - set(ledger))
    if missing:
        raise SystemExit(f"projection-digest ledger missing packageIds: {missing}")
    mismatched = []
    for package_id in committed_packages:
        feat = read_json(root / "generated/feat-inputs" / f"{package_id}.json")
        if feat.get("projectionDigest") != ledger[package_id].get("projectionDigest"):
            mismatched.append(package_id)
    if mismatched:
        raise SystemExit(f"projectionDigest mismatch against ledger: {mismatched}")


def pick_package(rows: dict[str, dict], status: str, generated: pathlib.Path) -> str:
    exact_status = sorted(pid for pid, row in rows.items() if row.get("status") == status)
    if not exact_status:
        raise SystemExit(f"no package-contract rows with status={status!r}")
    without_committed = [pid for pid in exact_status if not (generated / f"{pid}.json").exists()]
    return (without_committed or exact_status)[0]


def check_smoke(root: pathlib.Path, staged_root: pathlib.Path, rows: dict[str, dict], status: str, expected: str) -> None:
    package_id = pick_package(rows, status, root / "generated/feat-inputs")
    data = json.loads(run_make_feat_input(root, staged_root, package_id))
    if data.get("kind") != "feat.input.v1":
        raise SystemExit(f"{package_id}: kind mismatch: {data.get('kind')!r}")
    if data.get("status") != expected:
        raise SystemExit(f"{package_id}: status mismatch: {data.get('status')!r}, expected {expected!r}")
    if not data.get("sourceAuthority"):
        raise SystemExit(f"{package_id}: sourceAuthority missing")
    if not data.get("projectionDigest"):
        raise SystemExit(f"{package_id}: projectionDigest missing")
    if data.get("rawAdrDirectAuthority") is not False:
        raise SystemExit(f"{package_id}: rawAdrDirectAuthority must be false")


def check_accepted_set_non_decrease(root: pathlib.Path, base_package_contract: pathlib.Path) -> tuple[int, int]:
    head_rows = package_contracts(root / ROOT_REL_SPEC / "package-contract.v1.jsonl")
    base_rows = package_contracts(base_package_contract)
    base_accepted = {pid for pid, row in base_rows.items() if row.get("status") == "accepted"}
    head_accepted = {pid for pid, row in head_rows.items() if row.get("status") == "accepted"}
    lost = sorted(base_accepted - head_accepted)
    if lost:
        raise SystemExit(f"accepted packageIds dropped compared with base: {lost}")
    return len(base_accepted), len(head_accepted)


def report_source_authority(root: pathlib.Path, committed_packages: list[str]) -> None:
    values = {}
    for package_id in committed_packages:
        feat = read_json(root / "generated/feat-inputs" / f"{package_id}.json")
        values.setdefault(feat.get("sourceAuthority"), []).append(package_id)
    for source, packages in sorted(values.items(), key=lambda item: str(item[0])):
        print(
            "sourceAuthority-report: "
            f"{source!r} packages={len(packages)} status=INDETERMINATE until accepted non-governance owner exists"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="governance repo root")
    ap.add_argument(
        "--base-package-contract",
        help="optional base records/specs/package-contract.v1.jsonl for PR non-decrease check",
    )
    ap.add_argument(
        "--require-base",
        action="store_true",
        help="fail if --base-package-contract is omitted",
    )
    args = ap.parse_args()

    root = pathlib.Path(args.root).resolve()
    rows = package_contracts(root / ROOT_REL_SPEC / "package-contract.v1.jsonl")
    if not rows:
        raise SystemExit("package-contract ledger is empty")

    if args.require_base and not args.base_package_contract:
        raise SystemExit("--require-base was set but --base-package-contract was not provided")

    staged_root = stage_tool_layout(root)
    try:
        committed_packages = check_committed_projection(root, staged_root)
        check_projection_digest(root, committed_packages)
        check_smoke(root, staged_root, rows, "accepted", "ready")
        check_smoke(root, staged_root, rows, "planned", "planned-blocked")
        if args.base_package_contract:
            base_count, head_count = check_accepted_set_non_decrease(
                root,
                pathlib.Path(args.base_package_contract).resolve(),
            )
            print(f"accepted-set-non-decrease: PASS base={base_count} head={head_count}")
        else:
            print("accepted-set-non-decrease: skipped (no --base-package-contract)")
        report_source_authority(root, committed_packages)
        print(f"feat-input-continuity: PASS committed={len(committed_packages)} package-contracts={len(rows)}")
    finally:
        shutil.rmtree(staged_root, ignore_errors=True)


if __name__ == "__main__":
    main()
