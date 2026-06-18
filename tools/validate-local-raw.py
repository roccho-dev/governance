#!/usr/bin/env python3
"""validate-local-raw: governance function to validate feat-local raw.jsonl.

Validates a local raw.jsonl against the governance #AdrRaw CUE schema.
Output is governance.localRawValidation.v1 JSON, explicitly non-authoritative.

Exit 0 = all rows valid; exit 1 = validation errors found.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Validate feat-local raw.jsonl against governance #AdrRaw CUE schema")
    ap.add_argument("--raw", required=True, help="path to local raw.jsonl")
    ap.add_argument("--cue-dir", required=True,
                    help="path to governance CUE schema directory (policy/cue)")
    ap.add_argument("--out", default="-", help="output path (- for stdout)")
    args = ap.parse_args()

    raw_path = pathlib.Path(args.raw)
    cue_dir = pathlib.Path(args.cue_dir)

    if not raw_path.is_file():
        raise SystemExit(f"validate-local-raw: raw file not found: {raw_path}")
    if not cue_dir.is_dir():
        raise SystemExit(f"validate-local-raw: CUE schema dir not found: {cue_dir}")

    cue_files = sorted(str(p) for p in cue_dir.glob("*.cue"))
    if not cue_files:
        raise SystemExit(f"validate-local-raw: no .cue files in {cue_dir}")

    rows: list[tuple[int, dict]] = []
    for i, line in enumerate(raw_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append((i, json.loads(line)))
        except json.JSONDecodeError as e:
            rows.append((i, {"_parseError": str(e)}))

    errors: list[dict] = []
    valid_count = 0

    for lineno, row in rows:
        if "_parseError" in row:
            errors.append({"line": lineno, "error": row["_parseError"]})
            continue

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(row, f, ensure_ascii=False)
            tmp = pathlib.Path(f.name)

        try:
            result = subprocess.run(
                ["cue", "vet"] + cue_files + [str(tmp), "-d", "#AdrRaw"],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                errors.append({
                    "line": lineno,
                    "id": row.get("id") or row.get("adrId", "<unknown>"),
                    "error": result.stderr.strip(),
                })
            else:
                valid_count += 1
        finally:
            tmp.unlink(missing_ok=True)

    report = {
        "kind": "governance.localRawValidation.v1",
        "authoritative": False,
        "valid": len(errors) == 0,
        "totalRows": len(rows),
        "validRows": valid_count,
        "errors": errors,
        "note": "This validation result is non-authoritative. "
                "Local raw.jsonl must be proposed to adrs for acceptance.",
    }

    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out == "-":
        print(text, end="")
    else:
        pathlib.Path(args.out).write_text(text, encoding="utf-8")

    sys.exit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
