#!/usr/bin/env python3
"""Check README artifact conventions without generating or mutating files."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIRED_SECTIONS = [
    "Purpose",
    "Authority boundary",
    "Inputs",
    "Outputs / artifacts",
    "Checks",
    "Ownership / handoff",
]

BOUNDARY_TEXT = "README.md is a checked artifact"
NON_AUTHORITY_TEXT = "README.md is not an independent authority"


def heading_pattern(title: str) -> re.Pattern[str]:
    return re.compile(rf"^#+\s+{re.escape(title)}\s*$", re.IGNORECASE | re.MULTILINE)


def check_readme(path: Path, mode: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if mode not in {"checked_handwritten", "managed_block", "generated"}:
        return [{"code": "invalid-readme-mode", "path": str(path), "message": f"unsupported readme_mode: {mode}"}]
    if not path.exists():
        return [{"code": "readme-missing", "path": str(path), "message": "README file is missing"}]
    text = path.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        if not heading_pattern(section).search(text):
            findings.append({"code": "readme-section-missing", "path": str(path), "section": section})
    if BOUNDARY_TEXT not in text:
        findings.append({"code": "readme-boundary-missing", "path": str(path), "message": BOUNDARY_TEXT})
    if NON_AUTHORITY_TEXT not in text:
        findings.append({"code": "readme-non-authority-missing", "path": str(path), "message": NON_AUTHORITY_TEXT})
    if mode == "managed_block" and ("<!-- governance:readme:start -->" not in text or "<!-- governance:readme:end -->" not in text):
        findings.append({"code": "readme-managed-block-missing", "path": str(path)})
    if mode == "generated" and "generated" not in text.lower():
        findings.append({"code": "readme-generated-marker-missing", "path": str(path)})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readme", type=Path, required=True)
    parser.add_argument("--mode", required=True)
    args = parser.parse_args()
    findings = check_readme(args.readme, args.mode)
    report = {
        "kind": "governance.readmeArtifactCheck.v1",
        "status": "fail" if findings else "pass",
        "mode": args.mode,
        "readme": str(args.readme),
        "findings": findings,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
