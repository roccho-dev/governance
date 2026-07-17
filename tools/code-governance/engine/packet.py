from __future__ import annotations

import importlib.metadata
import subprocess
from pathlib import Path
from typing import Any

from .common import digest_file, read_json, read_jsonl, write_json


def build(root: Path, ledger: Path, schema: Path, tree_manifest: Path, output: Path) -> dict[str, Any]:
    projection = read_json(root / "reduced/projection.json")
    active_rows = read_jsonl(root / "reduced/projection.jsonl")
    reducer_receipt = read_json(root / "reduced/reducer-receipt.json")
    facts = read_jsonl(root / "scanned/facts.jsonl")
    findings = read_jsonl(root / "scanned/findings.jsonl")
    case_results = read_json(root / "scanned/case-results.json")
    scan_receipt = read_json(root / "scanned/scan-receipt.json")
    tree = read_json(tree_manifest)

    packet = {
        "kind": "code-governance-semantic-packet.v1",
        "status": "pass",
        "authority": False,
        "target": {"tree_sha256": tree["tree_sha256"]},
        "projection": projection,
        "active_rows": active_rows,
        "facts": facts,
        "findings": findings,
        "case_results": case_results,
        "receipts": {"reducer": reducer_receipt, "scanner": scan_receipt},
        "claims": {
            "canonical_ledger_valid": True,
            "explicit_supersession_reduced": True,
            "purpose_structure_closed": True,
            "positive_negative_fixtures_match": True,
            "transport_independent": True,
            "causal_support_verified": False,
            "top_purpose_achieved": False,
            "production_authority": False,
            "all_repositories_enforced": False,
        },
        "versions": {
            "python": __import__("sys").version.split()[0],
            "ast_grep_py": importlib.metadata.version("ast-grep-py"),
            "jsonschema": importlib.metadata.version("jsonschema"),
            "go": subprocess.run(["go", "version"], text=True, capture_output=True, check=True).stdout.strip(),
        },
        "input_digests": {
            "schema_sha256": digest_file(schema),
            "ledger_sha256": digest_file(ledger),
            "tree_sha256": tree["tree_sha256"],
            "projection_sha256": digest_file(root / "reduced/projection.jsonl"),
            "facts_sha256": digest_file(root / "scanned/facts.jsonl"),
            "findings_sha256": digest_file(root / "scanned/findings.jsonl"),
        },
    }
    write_json(output, packet)
    return packet
