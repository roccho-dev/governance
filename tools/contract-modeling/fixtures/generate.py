#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DECISION_DIGEST = "b72502f7845ead05f61d0640ef8b3f50789c7db0afafd3764b4c19d39a9fd4e0"
PURPOSE_PATH = [
    "purpose:P0",
    "purpose:P1",
    "purpose:P2",
    "purpose:P3",
    "purpose:P4",
    "purpose:M0",
]
LEGACY_IDS = [
    "schema-contracts",
    "field-contracts",
    "semantic-terms",
    "compatibility-edges",
    "migration-edges",
    "projection-contracts",
    "query-contracts",
    "destructive-cases",
    "model-decision-ledger",
    "promotion-ledger",
    "current-state",
    *[f"G{i:03d}" for i in range(1, 25)],
    "package-contract-abi",
]


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


LEGACY_DIGEST = digest(sorted(LEGACY_IDS))
PURPOSE_PATH_DIGEST = digest(PURPOSE_PATH)
assert LEGACY_DIGEST == "cfb47ace6877dfabe7322c18448962628611d26d328b81b5689b6c184e04e76d"


def row(row_id, row_kind, family, kind, subject, payload):
    return {
        "schema_ref": "contract-modeling/envelope.v1",
        "id": row_id,
        "row_kind": row_kind,
        "semantic_family": family,
        "semantic_kind": kind,
        "subject_key": subject,
        "payload": payload,
        "supersedes": [],
    }


def package(package_id, receipt_id, input_schema, output_schema, effects):
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


def model(request_id, model_id, identity, fields, terms, **options):
    return {
        "request_id": request_id,
        "proposed_model_id": model_id,
        "owner": "domain/modeling",
        "identity_keys": identity,
        "fields": fields,
        "terms": terms,
        "required_queries": options.get("queries", []),
        "requested_projection": options.get("projection"),
        "raw_direct_sql": options.get("raw", False),
        "witnesses": options.get("witnesses", []),
        "distinct_evidence": options.get("distinct", []),
        "destructive_case_ids": options.get("destructive", []),
        "migration_evidence": {
            "coverage": options.get("coverage", "none"),
            "round_trip": options.get("round_trip", False),
        },
        "purpose": {"start_id": "purpose:P0", "root_id": "purpose:M0"},
    }


def receipt(receipt_id, contract_payload, effectful):
    return {
        "receipt_id": receipt_id,
        "repository": "roccho-dev/governance",
        "candidate_sha": "@candidate",
        "status": "pass",
        "contract_digest": digest(contract_payload),
        "accepted_decision_digest": DECISION_DIGEST,
        "purpose_path_digest": PURPOSE_PATH_DIGEST,
        "expires_on": "2026-08-31",
        "effectful": effectful,
        "effect_readback_digest": "3" * 64 if effectful else None,
    }


def build():
    rows = []
    for purpose_id, is_root in [
        ("M0", True),
        ("P4", False),
        ("P3", False),
        ("P2", False),
        ("P1", False),
        ("P0", False),
    ]:
        subject = f"purpose:{purpose_id}"
        rows.append(
            row(
                subject,
                "subject",
                "purpose",
                "purpose-node",
                subject,
                {"display_name": purpose_id, "root": is_root},
            )
        )
    for child, parent in [
        ("P4", "M0"),
        ("P3", "P4"),
        ("P2", "P3"),
        ("P1", "P2"),
        ("P0", "P1"),
    ]:
        edge_id = f"purpose-edge:{child}:{parent}"
        rows.append(
            row(
                edge_id,
                "edge",
                "purpose",
                "purpose-parent",
                edge_id,
                {"child": f"purpose:{child}", "parent": f"purpose:{parent}"},
            )
        )

    graph_nodes = [
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
    for subject, kind, display_name in graph_nodes:
        rows.append(
            row(
                f"node:{subject}",
                "subject",
                "graph",
                kind,
                subject,
                {"display_name": display_name},
            )
        )
    for parent, child in [
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
    ]:
        edge_id = f"contains:{parent}:{child}"
        rows.append(
            row(
                edge_id,
                "edge",
                "graph",
                "contains",
                edge_id,
                {"parent": parent, "child": child},
            )
        )

    package_claims = [
        (
            "package-contract:code-governance",
            "contract:pkg:governance:code-governance",
            package(
                "pkg:governance:code-governance",
                "receipt:code-governance",
                "canonical-ledger.v1",
                "semantic-packet.v1",
                ["filesystem-read"],
            ),
            True,
        ),
        (
            "package-contract:claim-admission",
            "contract:pkg:governance:claim-admission",
            package(
                "pkg:governance:claim-admission",
                "receipt:claim-admission",
                "claim-port-input.v1",
                "claim-port-admission.v1",
                ["filesystem-read"],
            ),
            True,
        ),
        (
            "package-contract:model-only",
            "contract:pkg:governance:model-only-transform",
            package(
                "pkg:governance:model-only-transform",
                "receipt:model-only",
                "model-only.input.v1",
                "model-only.output.v1",
                ["none"],
            ),
            False,
        ),
    ]
    for claim_id, subject, payload, _ in package_claims:
        rows.append(
            row(
                claim_id,
                "claim",
                "package-contract-v1",
                "package-contract",
                subject,
                payload,
            )
        )

    requests = [
        model(
            "01-extend",
            "model:customer",
            ["customer_id"],
            ["customer_id", "name"],
            ["customer"],
            witnesses=["existing-use"],
        ),
        model(
            "02-semantic",
            "model:customer",
            ["customer_id"],
            ["customer_id", "name", "alias"],
            [],
            witnesses=["vocabulary-use"],
        ),
        model(
            "03-projection",
            "model:customer",
            ["customer_id"],
            ["customer_id", "name", "search"],
            ["customer-search"],
            projection="customer-search-v1",
            witnesses=["search-use"],
        ),
        model(
            "04-query",
            "model:customer",
            ["customer_id"],
            ["customer_id", "email"],
            ["email-search"],
            queries=["customer-by-email"],
            witnesses=["query-use"],
        ),
        model(
            "05-destructive",
            "model:customer",
            ["customer_id"],
            ["customer_id"],
            ["customer"],
            coverage="total",
            round_trip=False,
            witnesses=["breaking-use"],
        ),
        model(
            "06-new",
            "new:risk-assessment",
            ["assessment_id"],
            ["assessment_id", "customer_id", "score"],
            ["risk-assessment"],
            witnesses=["multiple-assessments"],
            distinct=["independent-lifecycle"],
        ),
        model(
            "07-ambiguous",
            "model:customer-account-link",
            ["customer_id"],
            ["customer_id", "account_id"],
            ["customer-account-link"],
        ),
        model(
            "08-raw",
            "model:customer",
            ["customer_id"],
            ["customer_id", "name"],
            ["customer"],
            queries=["raw-scan"],
            raw=True,
            witnesses=["request"],
        ),
    ]
    for payload in requests:
        request_id = payload["request_id"]
        rows.append(
            row(
                f"request:{request_id}",
                "claim",
                "data-model-v1",
                "model-request",
                f"request:{request_id}",
                payload,
            )
        )

    for _, _, payload, effectful in package_claims:
        receipt_id = payload["evidence"]["receipt_id"]
        rows.append(
            row(
                f"effect-receipt:{receipt_id}",
                "receipt",
                "effect",
                "effect-receipt",
                receipt_id,
                receipt(receipt_id, payload, effectful),
            )
        )

    legacy_rows = []
    for legacy_id in LEGACY_IDS:
        payload = {
            "legacy_id": legacy_id,
            "legacy_source_digest": LEGACY_DIGEST,
            "new_subject_key": f"new:{legacy_id}",
            "new_semantic_kind": "contract-modeling-v1",
            "disposition": "mapped",
            "reason": "mapped to recursive contract-modeling V1",
            "owner": "roccho-dev/governance",
            "accepted_decision_digest": DECISION_DIGEST,
        }
        legacy_row = row(
            f"legacy:{legacy_id}",
            "legacy-mapping",
            "migration",
            "legacy-responsibility",
            f"legacy:{legacy_id}",
            payload,
        )
        rows.append(legacy_row)
        legacy_rows.append(legacy_row)
    return rows, legacy_rows


def write_jsonl(path, values):
    path.write_text(
        "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for value in values
        ),
        encoding="utf-8",
    )


def main():
    rows, legacy_rows = build()
    write_jsonl(ROOT / "claims.jsonl", rows)
    write_jsonl(ROOT / "legacy-responsibilities.jsonl", legacy_rows)
    print(
        json.dumps(
            {
                "claims": len(rows),
                "legacy": len(legacy_rows),
                "legacyDigest": LEGACY_DIGEST,
                "purposePathDigest": PURPOSE_PATH_DIGEST,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
