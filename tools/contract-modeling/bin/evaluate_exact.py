#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def load_engine(path: Path):
    spec = importlib.util.spec_from_file_location("contract_modeling_engine", path)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load contract-modeling engine")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--require-duckdb", action="store_true")
    parser.add_argument("--claims", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    observed = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if observed != args.candidate_sha:
        raise SystemExit(f"candidate SHA mismatch: expected {args.candidate_sha}, observed {observed}")

    engine = load_engine(repo_root / "tools/contract-modeling/bin/engine.py")
    source = args.claims or repo_root / "tools/contract-modeling/fixtures/claims.jsonl"
    rows = engine.read_jsonl(source)
    rows.sort(key=lambda value: value["id"])
    with tempfile.TemporaryDirectory() as tmp:
        normalized = Path(tmp) / "claims.jsonl"
        normalized.write_text(
            "".join(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                    for value in rows),
            encoding="utf-8",
        )
        packet = engine.evaluate(
            args.candidate_sha,
            repo_root,
            claims_path=normalized,
            require_duckdb=args.require_duckdb,
        )
    engine.write_json(args.out, packet)
    print(engine.canonical_json(packet))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
