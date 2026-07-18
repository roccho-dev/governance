#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path


def load_engine(path: Path):
    spec = importlib.util.spec_from_file_location("contract_modeling_epoch", path)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load contract-modeling epoch engine")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def prove_package_policy_rejection(engine, candidate_sha: str, repo_root: Path, require_duckdb: bool) -> str:
    policy = engine.read_json(engine.FIXTURE_ROOT / "accepted-policy.json")
    rows = engine.read_jsonl(engine.FIXTURE_ROOT / "claims.jsonl")
    assertion = next(
        row
        for row in rows
        if row["semantic_family"] == "package-contract-v1"
        and row["payload"]["package_id"] == "pkg:governance:code-governance"
    )
    assertion["payload"]["effect"].append("provider-mutation")
    receipt_id = assertion["payload"]["evidence"]["receipt_id"]
    receipt = next(
        row
        for row in rows
        if row["semantic_kind"] == "effect-receipt"
        and row["payload"]["receipt_id"] == receipt_id
    )
    receipt["payload"]["contract_digest"] = engine.digest_value(assertion["payload"])

    with tempfile.TemporaryDirectory() as temporary:
        claims = Path(temporary) / "claims.jsonl"
        claims.write_text(
            "".join(engine.canonical_json(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        try:
            engine.evaluate(
                candidate_sha,
                repo_root,
                policy_path=engine.FIXTURE_ROOT / "accepted-policy.json",
                claims_path=claims,
                require_duckdb=require_duckdb,
            )
        except engine.ContractError as exc:
            reason = str(exc)
            if "required-package-contract-incomplete-or-weaker" not in reason:
                raise engine.ContractError(
                    f"package weakening failed for the wrong reason: {reason}"
                ) from exc
            return reason
    raise engine.ContractError("package weakening was admitted")


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

    policy_reason = prove_package_policy_rejection(
        engine, args.candidate_sha, repo_root, args.require_duckdb
    )
    for result in receipt.get("destructive_results", []):
        if result.get("name") == "package-weaker-than-policy":
            result["reason"] = policy_reason
            result["expected_reason"] = True
            break
    else:
        raise engine.ContractError("package-weaker-than-policy case is missing")
    receipt["expected_reason_cases"] = [
        {
            "name": "package-weaker-than-policy",
            "status": "pass",
            "reason": policy_reason,
        }
    ]

    engine.write_json(args.out, receipt)
    print(engine.canonical_json(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
