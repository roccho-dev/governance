#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def load_engine(path: Path):
    spec = importlib.util.spec_from_file_location("contract_modeling_epoch", path)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load contract-modeling epoch engine")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--require-duckdb", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    observed = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
    ).strip()
    if observed != args.candidate_sha:
        raise SystemExit(f"candidate SHA mismatch: expected {args.candidate_sha}, observed {observed}")

    engine = load_engine(repo_root / "tools/contract-modeling/bin/epoch.py")
    original_evaluate = engine.evaluate

    def exact_evaluate(candidate_sha, *rest, **kwargs):
        if candidate_sha != observed:
            raise engine.ContractError(
                f"candidate SHA mismatch: expected {observed}, got {candidate_sha}"
            )
        return original_evaluate(candidate_sha, *rest, **kwargs)

    engine.evaluate = exact_evaluate
    engine.strict.evaluate = exact_evaluate
    engine.strict.core.evaluate = exact_evaluate
    receipt = engine.selftest(args.candidate_sha, repo_root, args.require_duckdb)
    engine.write_json(args.out, receipt)
    print(engine.canonical_json(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
