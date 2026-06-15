#!/usr/bin/env python3
"""Shared declaration-driven CUE records gate.

Consumes an interface JSON array with {file, def, group, required} rows and
runs the common per-file plus relational CUE vet flow. This keeps governance
and downstream flakes from copying gate plumbing.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
from typing import Any


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
    return out


def run(cmd: list[str], cwd: pathlib.Path) -> None:
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="run shared CUE records gate from policy/interface.json")
    ap.add_argument("--root", default=".")
    ap.add_argument("--interface", default="policy/interface.json")
    ap.add_argument("--cue-dir", default="policy/cue")
    ap.add_argument("--relational-def", default="#All")
    ap.add_argument("--bundle-out", default=None)
    args = ap.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    interface_path = root / args.interface
    cue_dir = root / args.cue_dir
    entries = json.loads(interface_path.read_text(encoding="utf-8"))
    missing = [e["file"] for e in entries if e.get("required") and not (root / e["file"]).exists()]
    if missing:
        raise SystemExit("missing required record files: " + ", ".join(missing))
    cue_files = [str(path) for path in sorted(cue_dir.glob("*.cue"))]
    if not cue_files:
        raise SystemExit(f"no CUE policy files under {cue_dir}")

    vetted = 0
    for entry in entries:
        file = entry.get("file")
        definition = entry.get("def")
        if file and definition and (root / file).exists():
            run(["cue", "vet", *cue_files, file, "-d", definition], cwd=root)
            vetted += 1

    groups = sorted({e.get("group") for e in entries if e.get("group")})
    bundle: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        rows: list[dict[str, Any]] = []
        for entry in entries:
            if entry.get("group") != group:
                continue
            file = entry.get("file")
            if file and (root / file).exists():
                rows.extend(load_jsonl(root / file))
        bundle[str(group)] = rows

    bundle_out = pathlib.Path(args.bundle_out) if args.bundle_out else pathlib.Path(os.environ.get("TMPDIR", "/tmp")) / "relational-all.json"
    bundle_out.parent.mkdir(parents=True, exist_ok=True)
    bundle_out.write_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    run(["cue", "vet", *cue_files, str(bundle_out), "-d", args.relational_def], cwd=root)
    print(f"cue-records-gate: PASS per_file={vetted} groups={len(groups)} relational_def={args.relational_def}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
