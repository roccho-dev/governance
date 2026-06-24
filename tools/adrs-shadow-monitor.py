#!/usr/bin/env python3
"""Shadow monitor for ADRS input consumed by governance.

This script is intentionally read-only. It does not decide ADR authority and it does
not mutate ADRS, GitHub PRs, or governance state. It emits a JSON report that can be
used by governance CI as monitoring evidence.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any

REQUIRED_PATHS = [
    "flake.nix",
    "adr/schema.cue",
    "adr/allowed.cue",
    "adr/src/01JYJ5Q0ABCDE123456789ABCD-external-nix-package-build-contract.cue",
]


def utc_now() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def run_git(path: pathlib.Path, args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_required_file(root: pathlib.Path, rel: str) -> dict[str, Any]:
    path = root / rel
    if not path.is_file():
        return {
            "id": f"required-file:{rel}",
            "status": "alert",
            "severity": "error",
            "message": f"required ADRS input file is missing: {rel}",
        }
    return {
        "id": f"required-file:{rel}",
        "status": "ok",
        "sha256": sha256_file(path),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    adrs_path = pathlib.Path(args.adrs_path).resolve()
    checks: list[dict[str, Any]] = []

    if not adrs_path.exists():
        checks.append(
            {
                "id": "adrs-path-exists",
                "status": "alert",
                "severity": "error",
                "message": f"ADRS path does not exist: {adrs_path}",
            }
        )
    elif not adrs_path.is_dir():
        checks.append(
            {
                "id": "adrs-path-directory",
                "status": "alert",
                "severity": "error",
                "message": f"ADRS path is not a directory: {adrs_path}",
            }
        )
    else:
        checks.append({"id": "adrs-path-directory", "status": "ok"})
        for rel in REQUIRED_PATHS:
            checks.append(check_required_file(adrs_path, rel))

    resolved_sha = run_git(adrs_path, ["rev-parse", "HEAD"])
    gov_sha = os.environ.get("GITHUB_SHA") or None
    alerts = [c for c in checks if c.get("status") == "alert"]

    status = "clean" if not alerts else "alert"
    report: dict[str, Any] = {
        "kind": "governance.adrsShadowMonitor.report.v1",
        "status": status,
        "non_authority": True,
        "generated_at": utc_now(),
        "monitor": {
            "version": "adrs-shadow-monitor.v1",
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "gov_sha": gov_sha,
        },
        "adrs": {
            "path": str(adrs_path),
            "target_ref": args.target_ref,
            "resolved_sha": resolved_sha,
        },
        "boundary": {
            "authority": "adrs accepted decisions",
            "governance_role": "read-only shadow monitoring and projection evidence",
            "mutates_adrs": False,
            "mutates_github_prs": False,
            "blocks_adrs_pr": False,
        },
        "checks": checks,
        "alerts": alerts,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only ADRS shadow monitor checks.")
    parser.add_argument("--adrs-path", required=True, help="Path to checked-out ADRS input.")
    parser.add_argument("--target-ref", default="main", help="Observed ADRS ref, branch, PR ref, or SHA.")
    parser.add_argument("--report", required=True, help="Path to write JSON report.")
    parser.add_argument(
        "--fail-on-alert",
        action="store_true",
        help="Exit non-zero when monitoring alerts are found.",
    )
    args = parser.parse_args()

    report = build_report(args)
    report_path = pathlib.Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))

    if args.fail_on_alert and report["status"] != "clean":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
