#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ENGINE_PATH = Path(__file__).with_name("engine.py")
CURRENT_KEYS = {
    "current_epoch",
    "decision",
    "generated_by",
    "promotion_id",
    "subject_key",
}


def _load_engine():
    spec = importlib.util.spec_from_file_location("contract_modeling_strict_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load strict contract-modeling engine")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


strict = _load_engine()
_strict_evaluate = strict.evaluate


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _load_previous_current(
    policy: dict[str, Any], repo_root: Path
) -> list[dict[str, Any]]:
    contract = policy.get("previous_current")
    if not isinstance(contract, dict) or set(contract) != {"digest", "path"}:
        raise strict.ContractError("previous current contract must contain digest and path")

    root = repo_root.resolve()
    path = (root / contract["path"]).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise strict.ContractError("previous current path escapes repository root") from exc

    value = strict.read_json(path)
    if not isinstance(value, list):
        raise strict.ContractError("previous current must be an array")
    if strict.digest_value(value) != contract["digest"]:
        raise strict.ContractError("previous current digest mismatch")

    subjects: list[str] = []
    promotions: list[str] = []
    for index, row in enumerate(value):
        if not isinstance(row, dict) or set(row) != CURRENT_KEYS:
            raise strict.ContractError(
                f"previous current row {index} has an invalid closed shape"
            )
        if row["generated_by"] != "promotion-ledger":
            raise strict.ContractError(
                f"previous current row {index} is not promotion-derived"
            )
        if not all(isinstance(row[key], str) and row[key] for key in CURRENT_KEYS):
            raise strict.ContractError(
                f"previous current row {index} contains an empty identity"
            )
        subjects.append(row["subject_key"])
        promotions.append(row["promotion_id"])

    duplicate_subjects = _duplicates(subjects)
    if duplicate_subjects:
        raise strict.ContractError(
            f"duplicate previous current subjects: {duplicate_subjects}"
        )
    duplicate_promotions = _duplicates(promotions)
    if duplicate_promotions:
        raise strict.ContractError(
            f"duplicate previous promotion IDs: {duplicate_promotions}"
        )
    return sorted(value, key=lambda row: row["subject_key"])


def _apply_incrementally(
    previous: list[dict[str, Any]], promotions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    current = [dict(row) for row in previous]
    for promotion in promotions:
        current = strict.derive_current([promotion], current)
    return current


def _assert_quarantine_preservation(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
) -> list[str]:
    previous_by_subject = {row["subject_key"]: row for row in previous}
    current_by_subject = {row["subject_key"]: row for row in current}
    preserved: list[str] = []
    for decision in decisions:
        if decision["decision"] != "quarantine":
            continue
        subject = decision["subject_key"]
        old = previous_by_subject.get(subject)
        if old is None:
            continue
        if current_by_subject.get(subject) != old:
            raise strict.ContractError(
                f"quarantine changed previous current for {subject}"
            )
        preserved.append(subject)
    return sorted(preserved)


def evaluate(
    candidate_sha: str,
    repo_root: Path,
    policy_path: Path = strict.FIXTURE_ROOT / "accepted-policy.json",
    claims_path: Path = strict.FIXTURE_ROOT / "claims.jsonl",
    require_duckdb: bool = False,
) -> dict[str, Any]:
    policy = strict.read_json(policy_path)
    previous = _load_previous_current(policy, repo_root)
    packet = _strict_evaluate(
        candidate_sha,
        repo_root,
        policy_path,
        claims_path,
        require_duckdb,
    )

    full = strict.derive_current(packet["promotions"], previous)
    incremental = _apply_incrementally(previous, packet["promotions"])
    if strict.canonical_json(full) != strict.canonical_json(incremental):
        raise strict.ContractError("incremental current differs from full replay")

    preserved = _assert_quarantine_preservation(
        previous, full, packet["decisions"]
    )
    packet["previous_current"] = previous
    packet["previous_current_digest"] = strict.digest_value(previous)
    packet["current_state"] = full
    packet["current_digest"] = strict.digest_value(full)
    packet["incremental_digest"] = strict.digest_value(incremental)
    packet["replay_digest"] = packet["incremental_digest"]
    packet["replay_equal"] = True
    packet["quarantine_preserved_subjects"] = preserved
    packet.pop("semantic_digest", None)
    packet["semantic_digest"] = strict.digest_value(packet)
    return packet


for name in dir(strict):
    if not name.startswith("__"):
        globals()[name] = getattr(strict, name)

strict.evaluate = evaluate
strict.core.evaluate = evaluate
globals()["evaluate"] = evaluate


if __name__ == "__main__":
    raise SystemExit(strict.core.main())
