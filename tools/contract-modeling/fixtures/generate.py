#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIGEST = "b72502f7845ead05f61d0640ef8b3f50789c7db0afafd3764b4c19d39a9fd4e0"
LEGACY_DIGEST = "5555555555555555555555555555555555555555555555555555555555555555"


def row(row_id, row_kind, family, kind, subject, payload, supersedes=None):
    return {
        "schema_ref": "contract-modeling/envelope.v1",
        "id": row_id,
        "row_kind": row_kind,
        "semantic_family": family,
        "semantic_kind": kind,
        "subject_key": subject,
        "payload": payload,
        "supersedes": supersedes or [],
    }


def package_payload(package_id, receipt_id, input_schema, output_schema, effects):
    return {
        "package_id": package_id,
        "owner": "roccho-dev/governance",
        "input": [{"name": "input", "schema": input_schema, "version": "1"}],
        "output": [{"name": "output", "schema": output_schema, "version": "1"}],
        "error": [{"kind": "invalid-contract", "retryable": False}],
        "effect": effects,
        "dependency": ["python-stdlib"],
        "lifecycle": "active",
        "evidence": {
            "candidate_sha": "@candidate",
            "receipt_id": receipt_id,
            "expires_on": "2026-08-31",
        },
        "purpose": {"start_id": "purpose:P0", "root_id": "purpose:M0"},
        "waiver": None,
    }


def model_payload(request_id, model_id, identity, fields, terms, *, queries=None,
                  projection=None, raw=False, witnesses=None, distinct=None,
                  coverage="none", round_trip=False, destructive=None):
    return {
        "request_id": request_id,
        "proposed_model_id": model_id,
        "owner": "domain/modeling",
        "identity_keys": identity,
        "fields": fields,
        "terms": terms,
        "required_queries": queries or [],
        "requested_projection": projection,
        "raw_direct_sql": raw,
        "witnesses": witnesses or [],
        "distinct_evidence": distinct or [],
        "destructive_case_ids": destructive or [],
        "migration_evidence": {"coverage": coverage, "round_trip": round_trip},
        "purpose": {"start_id": "purpose:P0", "root_id": "purpose:M0"},
    }


def receipt(receipt_id, effectful=True):
    return {
        "receipt_id": receipt_id,
        "repository": "roccho-dev/governance",
        "candidate_sha": "@candidate",
        "status": "pass",
        "contract_digest": "1" * 64,
        "accepted_decision_digest": DIGEST,
        "purpose_path_digest": "2" * 64,
        "expires_on": "2026-08-31",
        "effectful": effectful,
        "effect_readback_digest": ("3" * 64) if effectful else None,
    }


def build():
    rows = []
    purposes = [
        ("purpose:M0", True),
        ("purpose:P4", False),
        ("purpose:P3", False),
        ("purpose:P2", False),
        ("purpose:P1", False),
        ("purpose:P0", False),
    ]
    for subject, is_root in purposes:
        rows.append(row(subject, "subject", "purpose", "purpose-node", subject,
                        {"display_name": subject.split(":")[-1], "root": is_root}))
    for child, parent in [
        ("purpose:P4", "purpose:M0"),
        ("purpose:P3", "purpose:P4"),
        ("purpose:P2", "purpose:P3"),
        ("purpose:P1", "purpose:P2"),
        ("purpose:P0", "purpose:P1"),
    ]:
        edge_id = f"purpose-edge:{child}:{parent}"
        rows.append(row(edge_id, "edge", "purpose", "purpose-parent", edge_id,
                        {"child": child, "parent": parent}))

    subjects = [
        ("org:roccho-dev", "organization", "roccho-dev"),
        ("repo:roccho-dev/governance", "repo", "governance"),
        ("pkg:governance:code-governance", "package", "code-governance"),
        ("module:code-governance:engine", "module", "engine"),
        ("component:code-governance:reducer", "component", "reducer"),
        ("operation:code-governance:evaluate", "operation", "evaluate"),
        ("pkg:governance:claim-admission", "package", "claim-admission"),
        ("module:claim-admission:compiler", "module", "compiler"),
        ("component:claim-admission:join", "component", "join"),
        ("operation:claim-admission:check", "operation", "check"),
        ("pkg:governance:model-only-transform", "package", "model-only-transform"),
    ]
    for subject, kind, name in subjects:
        rows.append(row(f"node:{subject}", "subject", "graph", kind, subject,
                        {"display_name": name}))
    contains = [
        ("org:roccho-dev", "repo:roccho-dev/governance"),
        ("repo:roccho-dev/governance", "pkg:governance:code-governance"),
        ("pkg:governance:code-governance", "module:code-governance:engine"),
        ("module:code-governance:engine", "component:code-governance:reducer"),
        ("component:code-governance:reducer", "operation:code-governance:evaluate"),
        ("repo:roccho-dev/governance", "pkg:governance:claim-admission"),
        ("pkg:governance:claim-admission", "module:claim-admission:compiler"),
        ("module:claim-admission:compiler", "component:claim-admission:join"),
        ("component:claim-admission:join", "operation:claim-admission:check"),
        ("repo:roccho-dev/governance", "pkg:governance:model-only-transform"),
    ]
    for parent, child in contains:
        edge_id = f"contains:{parent}:{child}"
        rows.append(row(edge_id, "edge", "graph", "contains", edge_id,
                        {"parent": parent, "child": child}))

    rows.extend([
        row("package-contract:code-governance", "claim", "package-contract-v1",
            "package-contract", "contract:pkg:governance:code-governance",
            package_payload("pkg:governance:code-governance", "receipt:code-governance",
                            "canonical-ledger.v1", "semantic-packet.v1", ["filesystem-read"])),
        row("package-contract:claim-admission", "claim", "package-contract-v1",
            "package-contract", "contract:pkg:governance:claim-admission",
            package_payload("pkg:governance:claim-admission", "receipt:claim-admission",
                            "claim-port-input.v1", "claim-port-admission.v1", ["filesystem-read"])),
        row("package-contract:model-only", "claim", "package-contract-v1",
            "package-contract", "contract:pkg:governance:model-only-transform",
            package_payload("pkg:governance:model-only-transform", "receipt:model-only",
                            "model-only.input.v1", "model-only.output.v1", ["none"])),
    ])

    claims = [
        model_payload("01-extend", "model:customer", ["customer_id"],
                      ["customer_id", "name"], ["customer"], witnesses=["existing-use"]),
        model_payload("02-semantic", "model:customer", ["customer_id"],
                      ["customer_id", "name", "alias"], [], witnesses=["vocabulary-use"]),
        model_payload("03-projection", "model:customer", ["customer_id"],
                      ["customer_id", "name", "search"], ["customer-search"],
                      projection="customer-search-v1", witnesses=["search-use"]),
        model_payload("04-query", "model:customer", ["customer_id"],
                      ["customer_id", "email"], ["email-search"],
                      queries=["customer-by-email"], witnesses=["query-use"]),
        model_payload("05-destructive", "model:customer", ["customer_id"],
                      ["customer_id"], ["customer"], coverage="total", round_trip=False,
                      witnesses=["breaking-use"]),
        model_payload("06-new", "new:risk-assessment", ["assessment_id"],
                      ["assessment_id", "customer_id", "score"], ["risk-assessment"],
                      witnesses=["multiple-assessments"], distinct=["independent-lifecycle"]),
        model_payload("07-ambiguous", "model:customer-account-link", ["customer_id"],
                      ["customer_id", "account_id"], ["customer-account-link"]),
        model_payload("08-raw", "model:customer", ["customer_id"],
                      ["customer_id", "name"], ["customer"],
                      queries=["raw-scan"], raw=True, witnesses=["request"]),
    ]
    for payload in claims:
        request_id = payload["request_id"]
        rows.append(row(f"request:{request_id}", "claim", "data-model-v1",
                        "model-request", f"request:{request_id}", payload))

    for receipt_id, effectful in [
        ("receipt:code-governance", True),
        ("receipt:claim-admission", True),
        ("receipt:model-only", False),
    ]:
        rows.append(row(f"effect-receipt:{receipt_id}", "receipt", "effect",
                        "effect-receipt", receipt_id, receipt(receipt_id, effectful)))

    legacy_ids = [
        "schema-contracts", "field-contracts", "semantic-terms",
        "compatibility-edges", "migration-edges", "projection-contracts",
        "query-contracts", "destructive-cases", "model-decision-ledger",
        "promotion-ledger", "current-state",
    ] + [f"G{i:03d}" for i in range(1, 25)] + ["package-contract-abi"]
    legacy_rows = []
    for legacy_id in legacy_ids:
        payload = {
            "legacy_id": legacy_id,
            "legacy_source_digest": LEGACY_DIGEST,
            "new_subject_key": f"new:{legacy_id}",
            "new_semantic_kind": "contract-modeling-v1",
            "disposition": "mapped",
            "reason": "mapped to recursive contract-modeling V1",
            "owner": "roccho-dev/governance",
            "accepted_decision_digest": DIGEST,
        }
        legacy_row = row(f"legacy:{legacy_id}", "legacy-mapping", "migration",
                         "legacy-responsibility", f"legacy:{legacy_id}", payload)
        rows.append(legacy_row)
        legacy_rows.append(legacy_row)
    return rows, legacy_rows


def main():
    rows, legacy_rows = build()
    for path, values in [
        (ROOT / "claims.jsonl", rows),
        (ROOT / "legacy-responsibilities.jsonl", legacy_rows),
    ]:
        path.write_text("".join(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
                                for value in values), encoding="utf-8")
    print(json.dumps({"claims": len(rows), "legacy": len(legacy_rows)}, sort_keys=True))


if __name__ == "__main__":
    main()
