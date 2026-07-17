from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .common import digest_file, read_json, read_jsonl, write_json, write_jsonl


class ReduceError(RuntimeError):
    pass


def _validate_schema(rows: list[dict[str, Any]], schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for index, row in enumerate(rows, start=1):
        for error in validator.iter_errors(row):
            path = ".".join(str(part) for part in error.absolute_path)
            errors.append(f"row {index}{'.' + path if path else ''}: {error.message}")
    if errors:
        raise ReduceError("schema validation failed:\n" + "\n".join(errors))


def reduce_rows(rows: list[dict[str, Any]], schema: dict[str, Any]) -> dict[str, Any]:
    _validate_schema(rows, schema)

    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = row["id"]
        if row_id in by_id:
            raise ReduceError(f"duplicate event id: {row_id}")
        by_id[row_id] = row

    superseded_by: dict[str, str] = {}
    for row in rows:
        for old_id in row["supersedes"]:
            old = by_id.get(old_id)
            if old is None:
                raise ReduceError(f"{row['id']} supersedes missing event {old_id}")
            if old["subject_key"] != row["subject_key"]:
                raise ReduceError(f"{row['id']} supersedes a different subject {old_id}")
            if old["row_kind"] != row["row_kind"] or old["semantic_kind"] != row["semantic_kind"]:
                raise ReduceError(f"{row['id']} changes row or semantic kind of {old_id}")
            if old_id in superseded_by:
                raise ReduceError(f"event {old_id} is superseded by multiple events")
            superseded_by[old_id] = row["id"]

    # Explicit supersession must be acyclic.
    for start in by_id:
        seen: set[str] = set()
        current = start
        while current in superseded_by:
            if current in seen:
                raise ReduceError(f"supersession cycle at {current}")
            seen.add(current)
            current = superseded_by[current]

    active = [row for row in rows if row["id"] not in superseded_by]
    active_by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in active:
        active_by_subject[row["subject_key"]].append(row)
    conflicts = {subject: items for subject, items in active_by_subject.items() if len(items) != 1}
    if conflicts:
        details = ", ".join(f"{subject}={len(items)}" for subject, items in sorted(conflicts.items()))
        raise ReduceError(f"active subject conflict: {details}")

    active_rows = sorted((items[0] for items in active_by_subject.values()), key=lambda row: row["subject_key"])
    contracts = [row for row in active_rows if row["semantic_kind"] == "fixture-contract"]
    if len(contracts) != 1:
        raise ReduceError(f"expected one active fixture contract, got {len(contracts)}")
    contract = contracts[0]

    purposes = {row["subject_key"]: row for row in active_rows if row["semantic_kind"] == "purpose"}
    rules = {row["subject_key"]: row for row in active_rows if row["semantic_kind"] == "code-rule"}
    cases = {row["subject_key"]: row for row in active_rows if row["semantic_kind"] == "test-case"}
    purpose_edges = [row for row in active_rows if row["semantic_kind"] == "purpose-parent"]
    rule_edges = [row for row in active_rows if row["semantic_kind"] == "rule-purpose"]

    if not purposes:
        raise ReduceError("no purposes")
    if not rules:
        raise ReduceError("no rules")
    if not cases:
        raise ReduceError("no cases")

    parent_of: dict[str, str] = {}
    for edge in purpose_edges:
        child = edge["payload"]["from_subject"]
        parent = edge["payload"]["to_subject"]
        if child not in purposes or parent not in purposes:
            raise ReduceError(f"purpose edge references missing node: {child} -> {parent}")
        if child == parent:
            raise ReduceError(f"purpose self-cycle: {child}")
        if child in parent_of:
            raise ReduceError(f"purpose has multiple parents: {child}")
        parent_of[child] = parent

    roots = sorted(set(purposes) - set(parent_of))
    if len(roots) != 1:
        raise ReduceError(f"expected one root purpose, got {roots}")
    root = roots[0]
    if root != contract["payload"]["top_purpose"]:
        raise ReduceError(f"contract top purpose {contract['payload']['top_purpose']} != graph root {root}")

    # Every purpose must terminate at the single root without a cycle.
    purpose_paths: dict[str, list[str]] = {}
    for purpose in purposes:
        path = [purpose]
        current = purpose
        seen = {purpose}
        while current in parent_of:
            current = parent_of[current]
            if current in seen:
                raise ReduceError(f"purpose cycle: {' -> '.join(path + [current])}")
            seen.add(current)
            path.append(current)
        if current != root:
            raise ReduceError(f"purpose {purpose} does not reach root {root}")
        purpose_paths[purpose] = path

    rule_to_purpose: dict[str, str] = {}
    for edge in rule_edges:
        rule = edge["payload"]["from_subject"]
        purpose = edge["payload"]["to_subject"]
        if rule not in rules or purpose not in purposes:
            raise ReduceError(f"rule-purpose edge references missing node: {rule} -> {purpose}")
        if rule in rule_to_purpose:
            raise ReduceError(f"rule has multiple immediate purposes: {rule}")
        rule_to_purpose[rule] = purpose
    missing_rule_edges = sorted(set(rules) - set(rule_to_purpose))
    if missing_rule_edges:
        raise ReduceError(f"rules without purpose: {missing_rule_edges}")

    rule_paths = {rule: purpose_paths[purpose] for rule, purpose in sorted(rule_to_purpose.items())}

    expected_cases = contract["payload"]["expected_cases"]
    if sorted(expected_cases) != sorted(cases):
        raise ReduceError(
            f"contract expected cases mismatch: expected {sorted(expected_cases)}, actual {sorted(cases)}"
        )

    return {
        "kind": "code-governance-projection.v1",
        "fixture_id": contract["payload"]["fixture_id"],
        "reducer_version": contract["payload"]["reducer_version"],
        "authority": False,
        "root_purpose": root,
        "purpose_structure_closed": True,
        "causal_support_verified": False,
        "top_purpose_achieved": False,
        "active_rows": active_rows,
        "active_event_ids": [row["id"] for row in active_rows],
        "superseded_event_ids": sorted(superseded_by),
        "purpose_paths": purpose_paths,
        "rule_paths": rule_paths,
        "counts": {
            "ledger_rows": len(rows),
            "active_rows": len(active_rows),
            "contracts": len(contracts),
            "purposes": len(purposes),
            "rules": len(rules),
            "cases": len(cases),
            "purpose_edges": len(purpose_edges),
            "rule_edges": len(rule_edges),
        },
    }


def run(ledger_path: Path, schema_path: Path, output_dir: Path) -> dict[str, Any]:
    rows = read_jsonl(ledger_path)
    schema = read_json(schema_path)
    projection = reduce_rows(rows, schema)
    output_dir.mkdir(parents=True, exist_ok=True)
    active_rows_path = output_dir / "projection.jsonl"
    write_jsonl(active_rows_path, projection["active_rows"])
    projection_for_file = {key: value for key, value in projection.items() if key != "active_rows"}
    write_json(output_dir / "projection.json", projection_for_file)
    receipt = {
        "kind": "code-governance-reducer-receipt.v1",
        "status": "pass",
        "authority": False,
        "schema_sha256": digest_file(schema_path),
        "ledger_sha256": digest_file(ledger_path),
        "projection_jsonl_sha256": digest_file(active_rows_path),
        "projection_json_sha256": digest_file(output_dir / "projection.json"),
        "reducer_version": projection["reducer_version"],
    }
    write_json(output_dir / "reducer-receipt.json", receipt)
    return projection


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.ledger, args.schema, args.output)
    except ReduceError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
