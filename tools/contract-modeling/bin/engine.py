#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any, Iterable

CORE_PATH = Path(__file__).with_name("contract_modeling.py")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROVIDER_ONLY_KEYS = {
    "actor",
    "comment_id",
    "issue_number",
    "pagination",
    "timestamp",
    "url",
    "workflow_run_id",
}

# (semantic_family, semantic_kind) -> (row_kind, exact payload keys or None when
# a closed JSON Schema owns the payload contract).
KIND_CONTRACTS: dict[tuple[str, str], tuple[str, frozenset[str] | None]] = {
    ("purpose", "purpose-node"): ("subject", frozenset({"display_name", "root"})),
    ("purpose", "purpose-parent"): ("edge", frozenset({"child", "parent"})),
    ("graph", "organization"): ("subject", frozenset({"display_name"})),
    ("graph", "repo"): ("subject", frozenset({"display_name"})),
    ("graph", "package"): ("subject", frozenset({"display_name"})),
    ("graph", "module"): ("subject", frozenset({"display_name"})),
    ("graph", "component"): ("subject", frozenset({"display_name"})),
    ("graph", "operation"): ("subject", frozenset({"display_name"})),
    ("graph", "contains"): ("edge", frozenset({"child", "parent"})),
    ("package-contract-v1", "package-contract"): ("claim", None),
    ("data-model-v1", "model-request"): ("claim", None),
    ("effect", "effect-receipt"): ("receipt", None),
    (
        "migration",
        "legacy-responsibility",
    ): (
        "legacy-mapping",
        frozenset(
            {
                "accepted_decision_digest",
                "disposition",
                "legacy_id",
                "legacy_source_digest",
                "new_semantic_kind",
                "new_subject_key",
                "owner",
                "reason",
            }
        ),
    ),
}


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
_original_validate_and_reduce = core.validate_and_reduce
_original_evaluate = core.evaluate


def _nested_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _nested_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nested_keys(child)


def _validate_row_contract(row: dict[str, Any]) -> None:
    contract = KIND_CONTRACTS.get((row.get("semantic_family"), row.get("semantic_kind")))
    if contract is None:
        raise core.ContractError(
            f"{row.get('id')}: unknown semantic family/kind "
            f"{row.get('semantic_family')}/{row.get('semantic_kind')}"
        )
    expected_row_kind, payload_keys = contract
    if row.get("row_kind") != expected_row_kind:
        raise core.ContractError(
            f"{row.get('id')}: {row.get('semantic_kind')} requires row_kind={expected_row_kind}"
        )
    payload = row.get("payload")
    if not isinstance(payload, dict):
        raise core.ContractError(f"{row.get('id')}: payload must be an object")

    nested = set(_nested_keys(payload))
    forbidden = sorted(core.FORBIDDEN_DERIVED_FIELDS.intersection(nested))
    if forbidden:
        raise core.ContractError(
            f"{row.get('id')}: forbidden trusted derived fields: {forbidden}"
        )
    provider = sorted(PROVIDER_ONLY_KEYS.intersection(nested))
    if provider:
        raise core.ContractError(
            f"{row.get('id')}: provider metadata is transport-only: {provider}"
        )
    if payload_keys is not None and set(payload) != payload_keys:
        raise core.ContractError(
            f"{row.get('id')}: closed payload keys required; "
            f"expected={sorted(payload_keys)} actual={sorted(payload)}"
        )


def _validate_graph_tree(active: dict[str, dict[str, Any]]) -> None:
    subjects = {
        key: row
        for key, row in active.items()
        if row["semantic_family"] == "graph" and row["row_kind"] == "subject"
    }
    roots = [key for key, row in subjects.items() if row["semantic_kind"] == "organization"]
    if len(roots) != 1:
        raise core.ContractError(f"graph needs exactly one organization root, got {roots}")
    root = roots[0]
    parent_of: dict[str, str] = {}
    for row in active.values():
        if row["semantic_family"] != "graph" or row["semantic_kind"] != "contains":
            continue
        parent_of[row["payload"]["child"]] = row["payload"]["parent"]
    if root in parent_of:
        raise core.ContractError(f"graph root may not have a parent: {root}")
    missing = sorted(subject for subject in subjects if subject != root and subject not in parent_of)
    if missing:
        raise core.ContractError(f"graph subjects missing containment parent: {missing}")
    for subject in subjects:
        current = subject
        seen: set[str] = set()
        while current != root:
            if current in seen:
                raise core.ContractError(f"containment cycle at {current}")
            seen.add(current)
            current = parent_of.get(current, "")
            if not current:
                raise core.ContractError(f"graph subject does not reach root: {subject}")


def _strict_validate_and_reduce(
    rows: list[dict[str, Any]], policy: dict[str, Any]
) -> Any:
    if core.jsonschema is None:
        raise core.ContractError("jsonschema dependency is required for fail-closed validation")
    for row in rows:
        _validate_row_contract(row)
    graph = _original_validate_and_reduce(rows, policy)
    _validate_graph_tree(graph.active_by_subject)
    return graph


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
    expected_source = policy["legacy"]["source_digest"]
    expected_decision = policy["decision"]["decision_digest"]
    if not isinstance(expected_source, str) or not HEX64.fullmatch(expected_source):
        raise core.ContractError("policy legacy source digest is invalid")

    count = 0
    for row in rows:
        if row.get("row_kind") != "legacy-mapping":
            continue
        count += 1
        payload = row.get("payload", {})
        if payload.get("legacy_source_digest") != expected_source:
            raise core.ContractError(
                f"{row.get('id')}: legacy row is not bound to the policy source digest"
            )
        if payload.get("accepted_decision_digest") != expected_decision:
            raise core.ContractError(
                f"{row.get('id')}: legacy row is not bound to the accepted decision"
            )
    if count == 0:
        raise core.ContractError("legacy migration ledger is empty")


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


core.validate_and_reduce = _strict_validate_and_reduce
core._purpose_paths = _strict_purpose_paths
core.evaluate = evaluate

for name in dir(core):
    if not name.startswith("__"):
        globals()[name] = getattr(core, name)


if __name__ == "__main__":
    raise SystemExit(core.main())
