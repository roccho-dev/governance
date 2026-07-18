#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable

CORE_PATH = Path(__file__).with_name("contract_modeling.py")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROVIDER_ONLY_KEYS = {
    "actor",
    "comment_id",
    "created_at",
    "issue_number",
    "pagination",
    "repository_url",
    "run_id",
    "timestamp",
    "updated_at",
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
_original_package_admission = core.derive_package_admission
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


def _strict_derive_admission(
    graph: Any, policy: dict[str, Any]
) -> list[dict[str, Any]]:
    claims = sorted(
        core._data_model_claims(graph), key=lambda row: row["payload"]["request_id"]
    )
    purpose_paths = _strict_purpose_paths(graph.active_by_subject)
    approved_models: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []

    for row in claims:
        payload = row["payload"]
        equivalent = [
            existing
            for existing in approved_models
            if core._model_similarity(payload, existing)
        ]
        ambiguous = (
            not payload["witnesses"]
            and not payload["distinct_evidence"]
            and bool(approved_models)
        )
        breaking = payload["migration_evidence"]["coverage"] != "none"
        migration_lossless = (
            payload["migration_evidence"]["coverage"] == "total"
            and payload["migration_evidence"]["round_trip"] is True
        )
        destructive_count = len(payload["destructive_case_ids"])
        query_present = bool(payload["required_queries"])
        projection_present = payload["requested_projection"] is not None

        if payload["raw_direct_sql"]:
            decision = "reject"
            reason = "raw direct production query is forbidden"
        elif equivalent:
            decision = "reject"
            reason = "equivalent existing model found"
        elif ambiguous:
            decision = "quarantine"
            reason = "equivalence and distinctness evidence is insufficient"
        elif breaking and (destructive_count == 0 or not migration_lossless):
            decision = "add_destructive_fixture"
            reason = "breaking change lacks complete destructive and lossless migration proof"
        elif projection_present and not query_present:
            decision = "add_projection"
            reason = "new stable projection surface is sufficient"
        elif query_present and not projection_present:
            decision = "add_query_contract"
            reason = "existing projected data needs a new query contract"
        elif not payload["terms"]:
            decision = "add_semantic_term"
            reason = "semantic vocabulary is missing"
        elif payload["proposed_model_id"].startswith("new:"):
            decision = "create_new_model"
            reason = "independent identity, lifecycle, and evidence justify a new model"
        else:
            decision = "extend_existing"
            reason = "existing model can satisfy the request by conservative extension"

        approved = decision not in {"reject", "quarantine", "add_destructive_fixture"}
        purpose = payload["purpose"]
        path = purpose_paths.get(purpose["start_id"])
        if not path or path[-1] != purpose["root_id"]:
            raise core.ContractError(
                f"{payload['request_id']}: declared purpose does not reach its root"
            )
        decisions.append(
            {
                "request_id": payload["request_id"],
                "subject_key": row["subject_key"],
                "owner": payload["owner"],
                "decision": decision,
                "reason": reason,
                "approved": approved,
                "equivalent_count": len(equivalent),
                "ambiguous": ambiguous,
                "breaking": breaking,
                "migration_lossless": migration_lossless,
                "destructive_count": destructive_count,
                "projection_present": projection_present,
                "query_present": query_present,
                "raw_direct_sql": payload["raw_direct_sql"],
                "purpose_path_digest": core.digest_value(path),
                "policy_digest": core.digest_value(policy["policy"]),
            }
        )
        if approved:
            approved_models.append(payload)
    return decisions


def _unique_by(values: list[str], label: str) -> None:
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise core.ContractError(f"duplicate {label}: {duplicates}")


def _strict_package_admission(
    graph: Any,
    policy: dict[str, Any],
    candidate_sha: str,
    repo_root: Path,
) -> list[dict[str, Any]]:
    universe = policy["required_package_universe"]
    _unique_by([row["packageId"] for row in universe], "required package IDs")
    assertions = core._package_assertions(graph)
    _unique_by([row["payload"]["package_id"] for row in assertions], "package assertions")
    receipt_rows = [
        row
        for row in graph.active_by_subject.values()
        if row["semantic_kind"] == "effect-receipt" and row["row_kind"] == "receipt"
    ]
    _unique_by([row["payload"]["receipt_id"] for row in receipt_rows], "receipt IDs")

    results = _original_package_admission(graph, policy, candidate_sha, repo_root)
    assertion_by_package = {
        row["payload"]["package_id"]: row["payload"] for row in assertions
    }
    receipts = {row["payload"]["receipt_id"]: row["payload"] for row in receipt_rows}
    purpose_paths = _strict_purpose_paths(graph.active_by_subject)
    evaluation_date = date.fromisoformat(policy["evaluation_date"])

    for result in results:
        payload = assertion_by_package[result["package_id"]]
        receipt = receipts[payload["evidence"]["receipt_id"]]
        if receipt["repository"] != result["repository"]:
            raise core.ContractError(f"{result['package_id']}: receipt repository mismatch")
        if receipt["contract_digest"] != core.digest_value(payload):
            raise core.ContractError(f"{result['package_id']}: receipt contract digest mismatch")
        path = purpose_paths.get(payload["purpose"]["start_id"])
        if not path or path[-1] != payload["purpose"]["root_id"]:
            raise core.ContractError(f"{result['package_id']}: invalid purpose path")
        if receipt["purpose_path_digest"] != core.digest_value(path):
            raise core.ContractError(f"{result['package_id']}: receipt purpose digest mismatch")
        if date.fromisoformat(receipt["expires_on"]) < evaluation_date:
            raise core.ContractError(f"{result['package_id']}: stale receipt")
        if date.fromisoformat(payload["evidence"]["expires_on"]) < evaluation_date:
            raise core.ContractError(f"{result['package_id']}: stale package evidence")
        if receipt["expires_on"] != payload["evidence"]["expires_on"]:
            raise core.ContractError(f"{result['package_id']}: receipt/evidence expiry mismatch")
        result["display_path"] = graph.display_paths.get(result["package_id"], "")
        if not result["display_path"]:
            raise core.ContractError(f"{result['package_id']}: package graph path missing")
        if payload["lifecycle"] != policy["organization_package_policy"]["required_lifecycle"]:
            result["weakens_policy"] = True
    return results


def _validate_legacy_bindings(policy: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    expected_source = policy["legacy"]["source_digest"]
    expected_decision = policy["decision"]["decision_digest"]
    if not isinstance(expected_source, str) or not HEX64.fullmatch(expected_source):
        raise core.ContractError("policy legacy source digest is invalid")

    legacy_ids: list[str] = []
    for row in rows:
        if row.get("row_kind") != "legacy-mapping":
            continue
        payload = row.get("payload", {})
        legacy_ids.append(payload.get("legacy_id", ""))
        if payload.get("legacy_source_digest") != expected_source:
            raise core.ContractError(
                f"{row.get('id')}: legacy row is not bound to the policy source digest"
            )
        if payload.get("accepted_decision_digest") != expected_decision:
            raise core.ContractError(
                f"{row.get('id')}: legacy row is not bound to the accepted decision"
            )
    if not legacy_ids:
        raise core.ContractError("legacy migration ledger is empty")
    _unique_by(legacy_ids, "legacy responsibility IDs")
    if core.digest_value(sorted(legacy_ids)) != expected_source:
        raise core.ContractError("legacy responsibility universe does not match source digest")


def evaluate(
    candidate_sha: str,
    repo_root: Path,
    policy_path: Path = core.FIXTURE_ROOT / "accepted-policy.json",
    claims_path: Path = core.FIXTURE_ROOT / "claims.jsonl",
    require_duckdb: bool = False,
) -> dict[str, Any]:
    policy = core.read_json(policy_path)
    rows = sorted(core.read_jsonl(claims_path), key=lambda row: row["id"])
    _validate_legacy_bindings(policy, rows)
    with tempfile.TemporaryDirectory() as temporary:
        normalized = Path(temporary) / "claims.jsonl"
        normalized.write_text(
            "".join(core.canonical_json(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        packet = _original_evaluate(
            candidate_sha,
            repo_root,
            policy_path,
            normalized,
            require_duckdb,
        )

    incremental: list[dict[str, Any]] = []
    for promotion in packet["promotions"]:
        incremental = core.derive_current([promotion], incremental)
    if core.canonical_json(incremental) != core.canonical_json(packet["current_state"]):
        raise core.ContractError("incremental current differs from full replay")
    packet["incremental_digest"] = core.digest_value(incremental)
    packet["replay_digest"] = packet["incremental_digest"]
    packet["replay_equal"] = True
    packet.pop("semantic_digest", None)
    packet["semantic_digest"] = core.digest_value(packet)
    return packet


core.validate_and_reduce = _strict_validate_and_reduce
core._purpose_paths = _strict_purpose_paths
core.derive_admission = _strict_derive_admission
core.derive_package_admission = _strict_package_admission
core.evaluate = evaluate

for name in dir(core):
    if not name.startswith("__"):
        globals()[name] = getattr(core, name)


if __name__ == "__main__":
    raise SystemExit(core.main())
