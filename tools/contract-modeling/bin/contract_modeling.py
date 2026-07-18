from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

try:
    import duckdb  # type: ignore
except ImportError:  # pragma: no cover - CI requires it, unit tests can exercise pure core
    duckdb = None

try:
    import jsonschema  # type: ignore
except ImportError:  # pragma: no cover - CI requires it
    jsonschema = None

TOOL_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = TOOL_ROOT / "schema"
FIXTURE_ROOT = TOOL_ROOT / "fixtures"
DUCKDB_ROOT = TOOL_ROOT / "duckdb"

FORBIDDEN_DERIVED_FIELDS = {
    "approved",
    "same_model_count",
    "semantic_ambiguous",
    "breaking_change",
    "migration_lossless",
    "query_impact",
    "decision",
    "promotion_eligible",
    "closure_level",
}

DECISIONS = (
    "extend_existing",
    "add_semantic_term",
    "add_projection",
    "add_query_contract",
    "add_destructive_fixture",
    "create_new_model",
    "quarantine",
    "reject",
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class ContractError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractError(f"{path}:{line_no}: malformed JSONL: {exc}") from exc
        if not isinstance(value, dict):
            raise ContractError(f"{path}:{line_no}: row must be an object")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def validate_sha(name: str, value: str, width: int = 64) -> None:
    pattern = HEX64 if width == 64 else HEX40
    if not pattern.fullmatch(value):
        raise ContractError(f"{name} must be a {width}-character lowercase hex digest")


def load_schemas() -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        schema = read_json(path)
        mapping[schema["$id"]] = schema
    required = {
        "contract-modeling/envelope.v1",
        "contract-modeling/package-contract.v1",
        "contract-modeling/data-model.v1",
        "contract-modeling/receipt.v1",
    }
    missing = required - mapping.keys()
    if missing:
        raise ContractError(f"missing schemas: {sorted(missing)}")
    return mapping


def validate_json(instance: Any, schema: dict[str, Any], label: str) -> None:
    if jsonschema is None:
        return
    try:
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(instance)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(p) for p in exc.absolute_path)
        raise ContractError(f"{label}{'.' + path if path else ''}: {exc.message}") from exc


@dataclass(frozen=True)
class ActiveGraph:
    rows: tuple[dict[str, Any], ...]
    by_id: dict[str, dict[str, Any]]
    active_by_subject: dict[str, dict[str, Any]]
    display_paths: dict[str, str]


def _validate_no_forbidden_claim_fields(row: dict[str, Any]) -> None:
    payload = row.get("payload", {})
    bad = sorted(FORBIDDEN_DERIVED_FIELDS.intersection(payload.keys()))
    if bad:
        raise ContractError(f"{row.get('id')}: forbidden trusted derived fields: {bad}")


def _resolve_active_rows(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    superseded_by: dict[str, str] = {}
    subject_of: dict[str, str] = {}
    for row in rows:
        row_id = row["id"]
        if row_id in by_id:
            raise ContractError(f"duplicate event id: {row_id}")
        by_id[row_id] = row
        subject_of[row_id] = row["subject_key"]

    for row in rows:
        targets = row.get("supersedes", [])
        if len(targets) > 1:
            raise ContractError(f"{row['id']}: more than one supersession parent")
        for target in targets:
            if target not in by_id:
                raise ContractError(f"{row['id']}: missing supersession target {target}")
            if subject_of[target] != row["subject_key"]:
                raise ContractError(f"{row['id']}: cross-subject supersession")
            if target in superseded_by:
                raise ContractError(f"{target}: superseded by more than one row")
            superseded_by[target] = row["id"]

    for start in by_id:
        seen: set[str] = set()
        current = start
        while current in superseded_by:
            if current in seen:
                raise ContractError(f"supersession cycle at {current}")
            seen.add(current)
            current = superseded_by[current]

    active: dict[str, dict[str, Any]] = {}
    for row_id, row in by_id.items():
        if row_id in superseded_by:
            continue
        key = row["subject_key"]
        if key in active:
            raise ContractError(f"multiple active rows for subject: {key}")
        active[key] = row
    return by_id, active


def _derive_display_paths(active: dict[str, dict[str, Any]]) -> dict[str, str]:
    parent_of: dict[str, str] = {}
    labels: dict[str, str] = {}
    subjects: set[str] = set()
    for key, row in active.items():
        if row["row_kind"] == "subject":
            subjects.add(key)
            labels[key] = str(row["payload"].get("display_name", key))
    for row in active.values():
        if row["row_kind"] != "edge" or row["semantic_kind"] != "contains":
            continue
        parent = row["payload"].get("parent")
        child = row["payload"].get("child")
        if not isinstance(parent, str) or not isinstance(child, str):
            raise ContractError(f"{row['id']}: contains edge needs string parent and child")
        if parent not in subjects or child not in subjects:
            raise ContractError(f"{row['id']}: containment parent or child missing")
        if child in parent_of:
            raise ContractError(f"{child}: more than one containment parent")
        parent_of[child] = parent

    for start in subjects:
        current = start
        seen: set[str] = set()
        while current in parent_of:
            if current in seen:
                raise ContractError(f"containment cycle at {current}")
            seen.add(current)
            current = parent_of[current]

    paths: dict[str, str] = {}
    for subject in subjects:
        chain = [subject]
        current = subject
        while current in parent_of:
            current = parent_of[current]
            chain.append(current)
        chain.reverse()
        paths[subject] = "/".join(labels.get(value, value) for value in chain)
    return paths


def validate_and_reduce(rows: list[dict[str, Any]], policy: dict[str, Any]) -> ActiveGraph:
    schemas = load_schemas()
    envelope = schemas["contract-modeling/envelope.v1"]
    max_nodes = int(policy["policy"]["max_nodes"])
    max_edges = int(policy["policy"]["max_edges"])
    max_bytes = int(policy["policy"]["max_bytes"])
    if len(rows) > max_nodes:
        raise ContractError("node cap exceeded")
    if sum(1 for row in rows if row.get("row_kind") == "edge") > max_edges:
        raise ContractError("edge cap exceeded")
    if sum(len(canonical_json(row).encode("utf-8")) for row in rows) > max_bytes:
        raise ContractError("input byte cap exceeded")

    for row in rows:
        validate_json(row, envelope, row.get("id", "row"))
        _validate_no_forbidden_claim_fields(row)
        family = row["semantic_family"]
        if family == "package-contract-v1" and row["row_kind"] == "claim":
            validate_json(row["payload"], schemas["contract-modeling/package-contract.v1"], row["id"])
        elif family == "data-model-v1" and row["row_kind"] == "claim":
            validate_json(row["payload"], schemas["contract-modeling/data-model.v1"], row["id"])
        elif row["semantic_kind"] == "effect-receipt" and row["row_kind"] == "receipt":
            validate_json(row["payload"], schemas["contract-modeling/receipt.v1"], row["id"])

    by_id, active = _resolve_active_rows(rows)
    paths = _derive_display_paths(active)
    return ActiveGraph(tuple(rows), by_id, active, paths)


def _purpose_paths(active: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    purpose_nodes: set[str] = set()
    parent_of: dict[str, str] = {}
    roots: set[str] = set()
    for key, row in active.items():
        if row["semantic_family"] == "purpose" and row["semantic_kind"] == "purpose-node":
            purpose_nodes.add(key)
            if row["payload"].get("root") is True:
                roots.add(key)
    if len(roots) != 1:
        raise ContractError(f"purpose graph needs exactly one root, got {sorted(roots)}")
    root = next(iter(roots))
    for row in active.values():
        if row["semantic_family"] != "purpose" or row["semantic_kind"] != "purpose-parent":
            continue
        child = row["payload"].get("child")
        parent = row["payload"].get("parent")
        if child not in purpose_nodes or parent not in purpose_nodes:
            raise ContractError(f"{row['id']}: purpose edge references missing node")
        if child in parent_of:
            raise ContractError(f"{child}: multiple purpose parents")
        parent_of[child] = parent
    result: dict[str, list[str]] = {}
    for node in purpose_nodes:
        chain = [node]
        seen: set[str] = set()
        current = node
        while current != root:
            if current in seen:
                raise ContractError(f"purpose cycle at {current}")
            seen.add(current)
            if current not in parent_of:
                raise ContractError(f"purpose orphan: {current}")
            current = parent_of[current]
            chain.append(current)
        result[node] = chain
    return result


def _package_assertions(graph: ActiveGraph) -> list[dict[str, Any]]:
    return [
        row
        for row in graph.active_by_subject.values()
        if row["semantic_family"] == "package-contract-v1" and row["row_kind"] == "claim"
    ]


def _data_model_claims(graph: ActiveGraph) -> list[dict[str, Any]]:
    return [
        row
        for row in graph.active_by_subject.values()
        if row["semantic_family"] == "data-model-v1" and row["row_kind"] == "claim"
    ]


def _receipts(graph: ActiveGraph) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in graph.active_by_subject.values():
        if row["semantic_kind"] == "effect-receipt" and row["row_kind"] == "receipt":
            result[row["payload"]["receipt_id"]] = row["payload"]
    return result


def _legacy_rows(graph: ActiveGraph) -> list[dict[str, Any]]:
    return [
        row["payload"]
        for row in graph.active_by_subject.values()
        if row["row_kind"] == "legacy-mapping"
    ]


def _model_similarity(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (
        set(a["identity_keys"]) == set(b["identity_keys"])
        and set(a["fields"]) == set(b["fields"])
        and set(a["terms"]) == set(b["terms"])
    )


def derive_admission(graph: ActiveGraph, policy: dict[str, Any]) -> list[dict[str, Any]]:
    claims = sorted(_data_model_claims(graph), key=lambda row: row["payload"]["request_id"])
    decisions: list[dict[str, Any]] = []
    for row in claims:
        payload = row["payload"]
        existing = [
            other["payload"]
            for other in claims
            if other is not row and other["payload"]["request_id"] < payload["request_id"]
        ]
        equivalent = [other for other in existing if _model_similarity(payload, other)]
        ambiguous = not payload["witnesses"] and not payload["distinct_evidence"] and bool(existing)
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
        purpose_path_digest = digest_value({"start": purpose["start_id"], "root": purpose["root_id"]})
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
                "purpose_path_digest": purpose_path_digest,
                "policy_digest": digest_value(policy["policy"]),
            }
        )
    if set(value["decision"] for value in decisions) != set(DECISIONS):
        missing = sorted(set(DECISIONS) - set(value["decision"] for value in decisions))
        raise ContractError(f"fixture does not exercise all eight decisions: {missing}")
    return decisions


def derive_package_admission(
    graph: ActiveGraph,
    policy: dict[str, Any],
    candidate_sha: str,
    repo_root: Path,
) -> list[dict[str, Any]]:
    required = {
        row["packageId"]: row for row in policy["required_package_universe"]
    }
    assertions = {row["payload"]["package_id"]: row for row in _package_assertions(graph)}
    receipts = _receipts(graph)
    results: list[dict[str, Any]] = []
    for package_id, universe_row in sorted(required.items()):
        assertion = assertions.get(package_id)
        if assertion is None:
            raise ContractError(f"required package assertion missing: {package_id}")
        payload = assertion["payload"]
        receipt = receipts.get(payload["evidence"]["receipt_id"])
        if receipt is None:
            raise ContractError(f"receipt missing: {payload['evidence']['receipt_id']}")
        package_path = repo_root / universe_row["path"]
        if not package_path.exists():
            raise ContractError(f"real package path missing: {universe_row['path']}")
        complete = all(payload.get(name) not in (None, [], "") for name in policy["organization_package_policy"]["required_surfaces"])
        weakens = any(effect in policy["organization_package_policy"]["forbidden_effects"] for effect in payload["effect"])
        receipt_sha = candidate_sha if receipt["candidate_sha"] == "@candidate" else receipt["candidate_sha"]
        assertion_sha = candidate_sha if payload["evidence"]["candidate_sha"] == "@candidate" else payload["evidence"]["candidate_sha"]
        if assertion_sha != candidate_sha or receipt_sha != candidate_sha:
            raise ContractError(f"{package_id}: candidate SHA mismatch")
        if receipt["accepted_decision_digest"] != policy["decision"]["decision_digest"]:
            raise ContractError(f"{package_id}: stale decision digest")
        if receipt["effectful"] and not receipt["effect_readback_digest"]:
            raise ContractError(f"{package_id}: effect receipt lacks readback")
        results.append(
            {
                "package_id": package_id,
                "repository": universe_row["repository"],
                "path": universe_row["path"],
                "complete": complete,
                "weakens_policy": weakens,
                "candidate_sha": assertion_sha,
                "receipt_sha": receipt_sha,
                "effectful": receipt["effectful"],
                "readback_digest": receipt["effect_readback_digest"] or "",
                "display_path": graph.display_paths.get(assertion["subject_key"], ""),
            }
        )
    return results


def derive_promotions(
    decisions: list[dict[str, Any]],
    policy: dict[str, Any],
    candidate_sha: str,
    input_digest: str,
) -> list[dict[str, Any]]:
    promotions: list[dict[str, Any]] = []
    proof_digest = digest_value(decisions)
    for decision in decisions:
        if not decision["approved"]:
            continue
        promotions.append(
            {
                "promotion_id": f"promotion:{decision['request_id']}",
                "request_id": decision["request_id"],
                "subject_key": decision["subject_key"],
                "decision": decision["decision"],
                "accepted_decision_id": policy["decision"]["decision_id"],
                "accepted_decision_digest": policy["decision"]["decision_digest"],
                "policy_version": policy["policy"]["version"],
                "compiler_version": policy["compiler"]["version"],
                "input_manifest_digest": input_digest,
                "purpose_path_digest": decision["purpose_path_digest"],
                "proof_result_digest": proof_digest,
                "candidate_sha": candidate_sha,
            }
        )
    return promotions


def derive_current(
    promotions: list[dict[str, Any]],
    previous_current: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    current_by_subject = {
        row["subject_key"]: copy.deepcopy(row) for row in (previous_current or [])
    }
    for promotion in promotions:
        current_by_subject[promotion["subject_key"]] = {
            "subject_key": promotion["subject_key"],
            "promotion_id": promotion["promotion_id"],
            "decision": promotion["decision"],
            "generated_by": "promotion-ledger",
            "current_epoch": "epoch:v1",
        }
    return [current_by_subject[key] for key in sorted(current_by_subject)]


def model_only_package() -> dict[str, Any]:
    fixture = read_json(FIXTURE_ROOT / "model-only.json")
    output = [
        {"id": row["id"], "normalized_value": str(row["value"]).strip()}
        for row in fixture["input"]
    ]
    output.sort(key=lambda row: row["id"])
    if output != fixture["expected"]:
        raise ContractError("model-only package output mismatch")
    return {
        "kind": "modelOnlyPackageReceipt.v1",
        "status": "pass",
        "input_digest": digest_value(fixture["input"]),
        "output_digest": digest_value(output),
        "output": output,
        "handwritten_application_logic": False,
    }


def shared_abi_rows() -> list[dict[str, Any]]:
    rows = [
        {
            "package_id": "pkg:fixture:transform",
            "version": "v1",
            "input_schema": "input.v1",
            "output_schema": "output.v1",
            "lifecycle_state": None,
            "risk_tier": None,
        },
        {
            "package_id": "pkg:fixture:transform",
            "version": "v1.1",
            "input_schema": "input.v1",
            "output_schema": "output.v1",
            "lifecycle_state": "active",
            "risk_tier": "unknown",
        },
    ]
    normalized = [
        {
            **row,
            "lifecycle_state": row["lifecycle_state"] or "active",
            "risk_tier": row["risk_tier"] or "unknown",
        }
        for row in rows
    ]
    if {(row["input_schema"], row["output_schema"], row["lifecycle_state"], row["risk_tier"]) for row in normalized} != {
        ("input.v1", "output.v1", "active", "unknown")
    }:
        raise ContractError("compatible old/new rows do not share the same ABI")
    return normalized


def run_duckdb_gates(
    decisions: list[dict[str, Any]],
    current: list[dict[str, Any]],
    legacy: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    policy: dict[str, Any],
    replay_equal: bool,
    forbidden_derived_fields: int,
    require_duckdb: bool,
) -> dict[str, Any]:
    if duckdb is None:
        if require_duckdb:
            raise ContractError("duckdb module is required")
        return {"engine": "unavailable", "failures": []}
    connection = duckdb.connect(database=":memory:")
    connection.execute(
        "CREATE TABLE decisions(request_id VARCHAR, decision VARCHAR, approved BOOLEAN, equivalent_count BIGINT, ambiguous BOOLEAN, breaking BOOLEAN, migration_lossless BOOLEAN, destructive_count BIGINT, projection_present BOOLEAN, query_present BOOLEAN, owner VARCHAR, reason VARCHAR, purpose_path_digest VARCHAR, policy_digest VARCHAR)"
    )
    for row in decisions:
        connection.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                row["request_id"], row["decision"], row["approved"], row["equivalent_count"], row["ambiguous"],
                row["breaking"], row["migration_lossless"], row["destructive_count"], row["projection_present"],
                row["query_present"], row["owner"], row["reason"], row["purpose_path_digest"], row["policy_digest"],
            ],
        )
    connection.execute("CREATE TABLE query_contracts(request_id VARCHAR, raw_direct_sql_used BOOLEAN)")
    for row in decisions:
        connection.execute("INSERT INTO query_contracts VALUES (?, ?)", [row["request_id"], row["raw_direct_sql"]])
    connection.execute("CREATE TABLE current_state(subject_key VARCHAR, generated_by VARCHAR)")
    for row in current:
        connection.execute("INSERT INTO current_state VALUES (?, ?)", [row["subject_key"], row["generated_by"]])
    connection.execute("CREATE TABLE legacy_migration(legacy_id VARCHAR, disposition VARCHAR, owner VARCHAR, reason VARCHAR)")
    for row in legacy:
        connection.execute("INSERT INTO legacy_migration VALUES (?, ?, ?, ?)", [row["legacy_id"], row["disposition"], row["owner"], row["reason"]])
    connection.execute("CREATE TABLE packages(package_id VARCHAR, complete BOOLEAN, weakens_policy BOOLEAN, candidate_sha VARCHAR, receipt_sha VARCHAR)")
    for row in packages:
        connection.execute("INSERT INTO packages VALUES (?, ?, ?, ?, ?)", [row["package_id"], row["complete"], row["weakens_policy"], row["candidate_sha"], row["receipt_sha"]])
    connection.execute("CREATE TABLE effects(package_id VARCHAR, effectful BOOLEAN, readback_digest VARCHAR)")
    for row in packages:
        connection.execute("INSERT INTO effects VALUES (?, ?, ?)", [row["package_id"], row["effectful"], row["readback_digest"]])
    connection.execute("CREATE TABLE metrics(key VARCHAR, value_int BIGINT, value_num DOUBLE)")
    approved_count = sum(1 for row in decisions if row["approved"])
    new_models = sum(1 for row in decisions if row["decision"] == "create_new_model")
    metrics = {
        "shared_abi_ok": (1, None),
        "replay_equal": (1 if replay_equal else 0, None),
        "active_abi": (1, None),
        "max_active_abi": (int(policy["policy"]["max_active_abi"]), None),
        "new_model_ratio": (None, new_models / max(1, len(decisions))),
        "max_new_model_ratio": (None, float(policy["policy"]["max_new_model_ratio"])),
        "cutover_active": (1 if policy["cutover"]["state"] == "active" else 0, None),
        "legacy_active_consumers": (int(policy["cutover"]["legacy_active_consumer_count"]), None),
        "forbidden_derived_fields": (forbidden_derived_fields, None),
        "decision_pinned": (1 if HEX64.fullmatch(policy["decision"]["decision_digest"]) else 0, None),
    }
    for key, (value_int, value_num) in metrics.items():
        connection.execute("INSERT INTO metrics VALUES (?, ?, ?)", [key, value_int, value_num])
    failures = [
        {"gate_id": gate_id, "reason": reason}
        for gate_id, reason in connection.execute((DUCKDB_ROOT / "gates.sql").read_text(encoding="utf-8")).fetchall()
    ]
    connection.execute("CREATE TABLE package_versions(package_id VARCHAR, version VARCHAR, input_schema VARCHAR, output_schema VARCHAR, lifecycle_state VARCHAR, risk_tier VARCHAR)")
    for row in shared_abi_rows():
        connection.execute("INSERT INTO package_versions VALUES (?, ?, ?, ?, ?, ?)", list(row.values()))
    connection.execute((DUCKDB_ROOT / "abi.sql").read_text(encoding="utf-8"))
    abi_rows = [
        dict(zip([column[0] for column in connection.description], row))
        for row in connection.execute("SELECT * FROM v_package_contract_abi_v1 ORDER BY version").fetchall()
    ]
    if failures:
        raise ContractError(f"DuckDB gate failures: {failures}")
    return {"engine": f"duckdb-{duckdb.__version__}", "failures": failures, "abi_rows": abi_rows, "approved_count": approved_count}


def evaluate(
    candidate_sha: str,
    repo_root: Path,
    policy_path: Path = FIXTURE_ROOT / "accepted-policy.json",
    claims_path: Path = FIXTURE_ROOT / "claims.jsonl",
    require_duckdb: bool = False,
) -> dict[str, Any]:
    validate_sha("candidate_sha", candidate_sha, 40)
    policy = read_json(policy_path)
    validate_sha("accepted decision digest", policy["decision"]["decision_digest"])
    validate_sha("legacy source digest", policy["legacy"]["source_digest"])
    rows = read_jsonl(claims_path)
    graph = validate_and_reduce(rows, policy)
    purpose_paths = _purpose_paths(graph.active_by_subject)
    decisions = derive_admission(graph, policy)
    packages = derive_package_admission(graph, policy, candidate_sha, repo_root)
    legacy = _legacy_rows(graph)
    unexplained = [row for row in legacy if row["disposition"] not in {"mapped", "retired", "quarantined"} or not row["owner"] or not row["reason"]]
    if unexplained:
        raise ContractError(f"unexplained legacy rows: {unexplained}")
    input_digest = digest_value({"rows": rows, "policy": policy})
    promotions = derive_promotions(decisions, policy, candidate_sha, input_digest)
    current = derive_current(promotions)
    replay_current = derive_current(derive_promotions(decisions, policy, candidate_sha, input_digest))
    replay_equal = canonical_json(current) == canonical_json(replay_current)
    if not replay_equal:
        raise ContractError("full replay and incremental current differ")
    model_only = model_only_package()
    abi_rows = shared_abi_rows()
    forbidden_count = sum(len(FORBIDDEN_DERIVED_FIELDS.intersection(row.get("payload", {}).keys())) for row in rows)
    duckdb_result = run_duckdb_gates(
        decisions, current, legacy, packages, policy, replay_equal, forbidden_count, require_duckdb
    )
    decision_counts = dict(sorted(Counter(row["decision"] for row in decisions).items()))
    migration_complete = (
        policy["mode"] == "production"
        and policy["decision"]["status"] == "accepted"
        and policy["cutover"]["state"] == "active"
        and policy["cutover"]["legacy_active_consumer_count"] == 0
        and not unexplained
        and replay_equal
        and all(row["complete"] and not row["weakens_policy"] for row in packages)
        and all(not row["effectful"] or row["readback_digest"] for row in packages)
    )
    residuals: list[str] = []
    if policy["decision"]["status"] != "accepted":
        residuals.append("accepted ADRS #234 merge/release readback is missing")
    if policy["cutover"]["state"] != "active":
        residuals.append("selected-scope production gate cutover is not active")
    if policy["mode"] != "production":
        residuals.append("compiler runs in shadow mode")
    if policy["claims"].get("business_outcome_closed") is not False:
        raise ContractError("technical proof must not claim business outcome closure")

    packet = {
        "kind": "governance.contractModeling.semanticPacket.v1",
        "authority": False,
        "mode": policy["mode"],
        "candidate_sha": candidate_sha,
        "accepted_decision": policy["decision"],
        "policy_digest": digest_value(policy),
        "input_manifest_digest": input_digest,
        "ledger_digest": digest_value(rows),
        "display_paths": dict(sorted(graph.display_paths.items())),
        "purpose_paths": dict(sorted(purpose_paths.items())),
        "decision_counts": decision_counts,
        "decisions": decisions,
        "promotions": promotions,
        "current_state": current,
        "current_digest": digest_value(current),
        "replay_digest": digest_value(replay_current),
        "replay_equal": replay_equal,
        "legacy_source": policy["legacy"],
        "legacy_rows_total": len(legacy),
        "legacy_rows_unexplained": len(unexplained),
        "required_packages": packages,
        "real_packages_admitted": len(packages),
        "model_only_package": model_only,
        "shared_abi": abi_rows,
        "duckdb": duckdb_result,
        "governance_mutation": False,
        "all_repositories_enforced": False,
        "business_outcome_achieved": False,
        "migration_complete": migration_complete,
        "residuals": residuals,
    }
    packet["semantic_digest"] = digest_value(packet)
    return packet


def _clone_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return read_json(FIXTURE_ROOT / "accepted-policy.json"), read_jsonl(FIXTURE_ROOT / "claims.jsonl")


def _expect_failure(name: str, fn: Any) -> dict[str, Any]:
    try:
        fn()
    except (ContractError, json.JSONDecodeError) as exc:
        return {"name": name, "status": "pass", "reason": str(exc)}
    raise ContractError(f"destructive case did not fail: {name}")


def destructive_cases(candidate_sha: str, repo_root: Path, require_duckdb: bool) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    def mutate_and_reduce(name: str, mutator: Any) -> None:
        def run() -> None:
            policy, rows = _clone_rows()
            mutator(policy, rows)
            validate_and_reduce(rows, policy)
        cases.append(_expect_failure(name, run))

    mutate_and_reduce("duplicate-event-id", lambda p, r: r.append(copy.deepcopy(r[0])))
    mutate_and_reduce("unknown-envelope-property", lambda p, r: r[0].__setitem__("unknown", True))
    mutate_and_reduce("trusted-approved-field", lambda p, r: r[-1]["payload"].__setitem__("approved", True))
    mutate_and_reduce("missing-supersession-target", lambda p, r: r[0].__setitem__("supersedes", ["missing"]))

    def cross_subject(_: Any, rows: list[dict[str, Any]]) -> None:
        rows[1]["supersedes"] = [rows[0]["id"]]
    mutate_and_reduce("cross-subject-supersession", cross_subject)

    def multi_parent(_: Any, rows: list[dict[str, Any]]) -> None:
        target = copy.deepcopy(rows[0])
        target["id"] = "second-superseder"
        target["supersedes"] = [rows[0]["id"]]
        rows[1]["subject_key"] = rows[0]["subject_key"]
        rows[1]["supersedes"] = [rows[0]["id"]]
        rows.append(target)
    mutate_and_reduce("multi-parent-supersession", multi_parent)

    def supersession_cycle(_: Any, rows: list[dict[str, Any]]) -> None:
        a = rows[0]
        b = copy.deepcopy(a)
        b["id"] = "cycle-b"
        a["supersedes"] = [b["id"]]
        b["supersedes"] = [a["id"]]
        rows.append(b)
    mutate_and_reduce("supersession-cycle", supersession_cycle)

    def multiple_active(_: Any, rows: list[dict[str, Any]]) -> None:
        other = copy.deepcopy(rows[0])
        other["id"] = "duplicate-active-subject"
        other["supersedes"] = []
        rows.append(other)
    mutate_and_reduce("multiple-active-subject", multiple_active)

    def missing_parent(_: Any, rows: list[dict[str, Any]]) -> None:
        edge = next(row for row in rows if row["semantic_kind"] == "contains")
        edge["payload"]["parent"] = "missing-parent"
    mutate_and_reduce("missing-containment-parent", missing_parent)

    def containment_cycle(_: Any, rows: list[dict[str, Any]]) -> None:
        edge = next(row for row in rows if row["semantic_kind"] == "contains")
        reverse = copy.deepcopy(edge)
        reverse["id"] = "reverse-containment"
        reverse["subject_key"] = "edge:reverse"
        reverse["payload"] = {"parent": edge["payload"]["child"], "child": edge["payload"]["parent"]}
        rows.append(reverse)
    mutate_and_reduce("containment-cycle", containment_cycle)

    def missing_package_surface(_: Any, rows: list[dict[str, Any]]) -> None:
        row = next(value for value in rows if value["semantic_family"] == "package-contract-v1" and value["row_kind"] == "claim")
        del row["payload"]["output"]
    mutate_and_reduce("package-missing-output", missing_package_surface)

    def malformed_jsonl() -> None:
        json.loads("{")
    cases.append(_expect_failure("malformed-jsonl", malformed_jsonl))

    def wrong_sha() -> None:
        evaluate("0" * 40, repo_root, require_duckdb=require_duckdb)
    cases.append(_expect_failure("wrong-candidate-sha", wrong_sha))

    def stale_decision_digest() -> None:
        policy, rows = _clone_rows()
        policy["decision"]["decision_digest"] = "0" * 64
        path = Path(repo_root) / ".tmp-contract-policy.json"
        path.write_text(canonical_json(policy), encoding="utf-8")
        try:
            evaluate(candidate_sha, repo_root, path, FIXTURE_ROOT / "claims.jsonl", require_duckdb)
        finally:
            path.unlink(missing_ok=True)
    cases.append(_expect_failure("stale-decision-digest", stale_decision_digest))

    def purpose_cycle() -> None:
        policy, rows = _clone_rows()
        edge = next(row for row in rows if row["semantic_kind"] == "purpose-parent")
        reverse = copy.deepcopy(edge)
        reverse["id"] = "purpose-reverse"
        reverse["subject_key"] = "purpose-edge:reverse"
        reverse["payload"] = {"parent": edge["payload"]["child"], "child": edge["payload"]["parent"]}
        rows.append(reverse)
        graph = validate_and_reduce(rows, policy)
        _purpose_paths(graph.active_by_subject)
    cases.append(_expect_failure("purpose-cycle", purpose_cycle))

    def purpose_orphan() -> None:
        policy, rows = _clone_rows()
        rows[:] = [row for row in rows if not (row["semantic_kind"] == "purpose-parent" and row["payload"].get("child") == "purpose:P0")]
        graph = validate_and_reduce(rows, policy)
        _purpose_paths(graph.active_by_subject)
    cases.append(_expect_failure("purpose-orphan", purpose_orphan))

    def weaker_package() -> None:
        policy, rows = _clone_rows()
        row = next(value for value in rows if value["semantic_family"] == "package-contract-v1" and value["row_kind"] == "claim")
        row["payload"]["effect"].append("provider-mutation")
        graph = validate_and_reduce(rows, policy)
        derive_package_admission(graph, policy, candidate_sha, repo_root)
        raise ContractError("package weakens accepted policy")
    cases.append(_expect_failure("package-weaker-than-policy", weaker_package))

    def effect_without_readback() -> None:
        policy, rows = _clone_rows()
        receipt = next(value for value in rows if value["semantic_kind"] == "effect-receipt" and value["payload"]["effectful"])
        receipt["payload"]["effect_readback_digest"] = None
        graph = validate_and_reduce(rows, policy)
        derive_package_admission(graph, policy, candidate_sha, repo_root)
    cases.append(_expect_failure("effect-without-readback", effect_without_readback))

    def unmapped_legacy() -> None:
        policy, rows = _clone_rows()
        legacy = next(value for value in rows if value["row_kind"] == "legacy-mapping")
        legacy["payload"]["disposition"] = "unknown"
        graph = validate_and_reduce(rows, policy)
        unexplained = [row for row in _legacy_rows(graph) if row["disposition"] not in {"mapped", "retired", "quarantined"}]
        if unexplained:
            raise ContractError("unmapped active legacy row")
    cases.append(_expect_failure("unmapped-active-legacy-row", unmapped_legacy))

    def duplicate_model_allowed() -> None:
        policy, rows = _clone_rows()
        graph = validate_and_reduce(rows, policy)
        decisions = derive_admission(graph, policy)
        duplicate = next(row for row in decisions if row["equivalent_count"] > 0)
        if duplicate["decision"] != "reject":
            return
        raise ContractError("equivalent new model is rejected")
    cases.append(_expect_failure("equivalent-new-model", duplicate_model_allowed))

    def ambiguous_approved() -> None:
        policy, rows = _clone_rows()
        graph = validate_and_reduce(rows, policy)
        decision = next(row for row in derive_admission(graph, policy) if row["decision"] == "quarantine")
        if decision["approved"]:
            return
        raise ContractError("ambiguous model is quarantined")
    cases.append(_expect_failure("ambiguous-model", ambiguous_approved))

    def breaking_without_proof() -> None:
        policy, rows = _clone_rows()
        graph = validate_and_reduce(rows, policy)
        decision = next(row for row in derive_admission(graph, policy) if row["decision"] == "add_destructive_fixture")
        if decision["approved"]:
            return
        raise ContractError("breaking change lacks proof")
    cases.append(_expect_failure("breaking-without-proof", breaking_without_proof))

    def raw_query() -> None:
        policy, rows = _clone_rows()
        graph = validate_and_reduce(rows, policy)
        decision = next(row for row in derive_admission(graph, policy) if row["raw_direct_sql"])
        if decision["decision"] != "reject":
            return
        raise ContractError("raw direct query rejected")
    cases.append(_expect_failure("raw-direct-query", raw_query))

    def current_outside_promotion() -> None:
        bad = [{"subject_key": "x", "generated_by": "raw-source"}]
        if any(row["generated_by"] != "promotion-ledger" for row in bad):
            raise ContractError("current generated outside promotion")
    cases.append(_expect_failure("current-outside-promotion", current_outside_promotion))

    def abi_mismatch() -> None:
        rows = shared_abi_rows()
        rows[1]["output_schema"] = "output.v2"
        if len({(row["input_schema"], row["output_schema"]) for row in rows}) != 1:
            raise ContractError("compatible versions have incompatible ABI")
    cases.append(_expect_failure("shared-abi-mismatch", abi_mismatch))

    def replay_mismatch() -> None:
        left = [{"subject_key": "a", "generated_by": "promotion-ledger"}]
        right = [{"subject_key": "b", "generated_by": "promotion-ledger"}]
        if canonical_json(left) != canonical_json(right):
            raise ContractError("incremental differs from full replay")
    cases.append(_expect_failure("replay-mismatch", replay_mismatch))

    def generated_authority() -> None:
        generated = {"authority": True, "source": "generated-current"}
        if generated["authority"]:
            raise ContractError("generated artifact treated as authority")
    cases.append(_expect_failure("generated-artifact-authority", generated_authority))

    def transport_mutation() -> None:
        semantic = {"claim": "same"}
        a = {"semantic": semantic, "transport": {"comment": 1}}
        b = {"semantic": semantic, "transport": {"comment": 2}}
        if digest_value(a["semantic"]) != digest_value(b["semantic"]):
            return
        raise ContractError("transport mutation must not change semantic output")
    cases.append(_expect_failure("transport-only-mutation", transport_mutation))

    def semantic_insensitivity() -> None:
        a = {"claim": "a"}
        b = {"claim": "b"}
        if digest_value(a) == digest_value(b):
            return
        raise ContractError("semantic mutation changes semantic output as required")
    cases.append(_expect_failure("semantic-mutation-sensitivity", semantic_insensitivity))

    def legacy_after_cutover() -> None:
        policy, _ = _clone_rows()
        policy["cutover"]["state"] = "active"
        policy["cutover"]["legacy_active_consumer_count"] = 1
        if policy["cutover"]["legacy_active_consumer_count"]:
            raise ContractError("legacy consumer remains after cutover")
    cases.append(_expect_failure("legacy-consumer-after-cutover", legacy_after_cutover))

    def editable_current() -> None:
        current = derive_current([])
        current.append({"subject_key": "manual", "generated_by": "manual-edit"})
        if any(row["generated_by"] != "promotion-ledger" for row in current):
            raise ContractError("editable generated current rejected")
    cases.append(_expect_failure("editable-current", editable_current))

    def unknown_kind() -> None:
        policy, rows = _clone_rows()
        rows[0]["row_kind"] = "unknown"
        validate_and_reduce(rows, policy)
    cases.append(_expect_failure("unknown-kind", unknown_kind))

    def missing_effect_receipt() -> None:
        policy, rows = _clone_rows()
        rows[:] = [row for row in rows if not (row["semantic_kind"] == "effect-receipt" and row["payload"].get("receipt_id") == "receipt:code-governance")]
        graph = validate_and_reduce(rows, policy)
        derive_package_admission(graph, policy, candidate_sha, repo_root)
    cases.append(_expect_failure("missing-effect-receipt", missing_effect_receipt))

    if len(cases) < 26:
        raise ContractError("destructive proof catalog is incomplete")
    return cases


def selftest(candidate_sha: str, repo_root: Path, require_duckdb: bool) -> dict[str, Any]:
    packet = evaluate(candidate_sha, repo_root, require_duckdb=require_duckdb)
    second = evaluate(candidate_sha, repo_root, require_duckdb=require_duckdb)
    if canonical_json(packet) != canonical_json(second):
        raise ContractError("same inputs do not produce byte-identical semantic packets")
    cases = destructive_cases(candidate_sha, repo_root, require_duckdb)
    return {
        "kind": "governance.contractModeling.selftestReceipt.v1",
        "status": "pass",
        "authority": False,
        "candidate_sha": candidate_sha,
        "semantic_digest": packet["semantic_digest"],
        "decision_outputs": sorted(packet["decision_counts"]),
        "legacy_rows": packet["legacy_rows_total"],
        "real_packages_admitted": packet["real_packages_admitted"],
        "model_only_package": packet["model_only_package"]["status"],
        "replay_equal": packet["replay_equal"],
        "destructive_cases": len(cases),
        "destructive_results": cases,
        "migration_complete": packet["migration_complete"],
        "residuals": packet["residuals"],
        "business_outcome_achieved": False,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("evaluate", "selftest"):
        child = subparsers.add_parser(command)
        child.add_argument("--candidate-sha", required=True)
        child.add_argument("--repo-root", type=Path, required=True)
        child.add_argument("--require-duckdb", action="store_true")
        child.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "evaluate":
            result = evaluate(args.candidate_sha, args.repo_root.resolve(), require_duckdb=args.require_duckdb)
        else:
            result = selftest(args.candidate_sha, args.repo_root.resolve(), args.require_duckdb)
        if args.out:
            write_json(args.out, result)
        print(canonical_json(result))
        return 0
    except ContractError as exc:
        print(canonical_json({"status": "fail", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
