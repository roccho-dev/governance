#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

CORE_PATH = Path(__file__).with_name("contract_modeling.py")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _load_core():
    spec = importlib.util.spec_from_file_location("contract_modeling_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load contract-modeling core")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


core = _load_core()
_original_purpose_paths = core._purpose_paths
_original_evaluate = core.evaluate


def _strict_purpose_paths(active: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    roots = {
        key
        for key, row in active.items()
        if row["semantic_family"] == "purpose"
        and row["semantic_kind"] == "purpose-node"
        and row["payload"].get("root") is True
    }
    if len(roots) == 1:
        root = next(iter(roots))
        for row in active.values():
            if (
                row["semantic_family"] == "purpose"
                and row["semantic_kind"] == "purpose-parent"
                and row["payload"].get("child") == root
            ):
                raise core.ContractError(f"purpose root may not have a parent: {root}")
    return _original_purpose_paths(active)


def _validate_legacy_bindings(policy: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    expected_decision = policy["decision"]["decision_digest"]
    source_digests: set[str] = set()
    count = 0
    for row in rows:
        if row.get("row_kind") != "legacy-mapping":
            continue
        count += 1
        payload = row.get("payload", {})
        source_digest = payload.get("legacy_source_digest")
        if not isinstance(source_digest, str) or not HEX64.fullmatch(source_digest):
            raise core.ContractError(f"{row.get('id')}: invalid legacy source digest")
        source_digests.add(source_digest)
        if payload.get("accepted_decision_digest") != expected_decision:
            raise core.ContractError(
                f"{row.get('id')}: legacy row is not bound to the accepted decision"
            )
    if count == 0:
        raise core.ContractError("legacy migration ledger is empty")
    if len(source_digests) != 1:
        raise core.ContractError("legacy rows do not bind one frozen proof-corpus source")


def evaluate(
    candidate_sha: str,
    repo_root: Path,
    policy_path: Path = core.FIXTURE_ROOT / "accepted-policy.json",
    claims_path: Path = core.FIXTURE_ROOT / "claims.jsonl",
    require_duckdb: bool = False,
) -> dict[str, Any]:
    policy = core.read_json(policy_path)
    rows = core.read_jsonl(claims_path)
    _validate_legacy_bindings(policy, rows)
    return _original_evaluate(
        candidate_sha,
        repo_root,
        policy_path,
        claims_path,
        require_duckdb,
    )


core._purpose_paths = _strict_purpose_paths
core.evaluate = evaluate

for name in dir(core):
    if not name.startswith("__"):
        globals()[name] = getattr(core, name)


if __name__ == "__main__":
    raise SystemExit(core.main())
