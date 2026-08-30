from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .core import ContractError, Fixture, canonical_json, load_fixture, sha256_bytes, validate_fixture

OUTPUT_FILE = "package-obligations.jsonl"
RECEIPT_FILE = "package-obligations-materialization.json"
RECEIPT_FIELDS = {
    "kind",
    "status",
    "fixture_id",
    "source_file",
    "source_sha256",
    "output_file",
    "output_sha256",
    "row_count",
    "package_ids_sha256",
    "active_package_ids",
    "target_repository",
    "target_commit",
    "target_tree",
    "target_system",
    "inventory_algorithm",
    "authority",
    "accepted_meaning_authority",
    "production_gate",
    "boundary",
    "receipt_digest",
}


def _package_ids_digest(fixture: Fixture) -> str:
    value = ("\n".join(row["package_id"] for row in fixture.rows) + "\n").encode("utf-8")
    return sha256_bytes(value)


def receipt_base(fixture: Fixture) -> dict[str, Any]:
    manifest = fixture.manifest
    return {
        "kind": "governance.packageObligationMaterializationReceipt.v1",
        "status": "pass",
        "fixture_id": manifest["fixture_id"],
        "source_file": manifest["source_file"],
        "source_sha256": manifest["source_sha256"],
        "output_file": OUTPUT_FILE,
        "output_sha256": sha256_bytes(fixture.source_bytes),
        "row_count": len(fixture.rows),
        "package_ids_sha256": _package_ids_digest(fixture),
        "active_package_ids": list(manifest["active_package_ids"]),
        "target_repository": manifest["target_repository"],
        "target_commit": manifest["target_commit"],
        "target_tree": manifest["target_tree"],
        "target_system": manifest["target_system"],
        "inventory_algorithm": manifest["inventory_algorithm"],
        "authority": False,
        "accepted_meaning_authority": False,
        "production_gate": False,
        "boundary": "validated fixture bytes are projected without semantic reinterpretation; receipt proves deterministic materialization only",
    }


def receipt_digest(value: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def build_receipt(fixture: Fixture) -> dict[str, Any]:
    base = receipt_base(fixture)
    return {**base, "receipt_digest": receipt_digest(base)}


def validate_receipt(receipt: dict[str, Any], output_bytes: bytes, fixture: Fixture) -> None:
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
        raise ContractError("materialization-receipt-fields")
    if receipt["kind"] != "governance.packageObligationMaterializationReceipt.v1" or receipt["status"] != "pass":
        raise ContractError("materialization-receipt-state")
    expected = build_receipt(fixture)
    if receipt != expected:
        raise ContractError("materialization-receipt-drift")
    if output_bytes != fixture.source_bytes:
        raise ContractError("materialization-output-byte-drift")
    if sha256_bytes(output_bytes) != receipt["output_sha256"]:
        raise ContractError("materialization-output-digest")


def materialize(fixture_dir: Path, out_dir: Path) -> dict[str, Any]:
    fixture_dir = fixture_dir.resolve()
    out_dir = out_dir.resolve()
    if out_dir == fixture_dir or fixture_dir in out_dir.parents:
        raise ContractError("materialization-output-inside-fixture")
    fixture = load_fixture(fixture_dir)
    parent = out_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{out_dir.name}.", dir=parent))
    try:
        (staging / OUTPUT_FILE).write_bytes(fixture.source_bytes)
        receipt = build_receipt(fixture)
        (staging / RECEIPT_FILE).write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        validate_receipt(receipt, (staging / OUTPUT_FILE).read_bytes(), fixture)
        if out_dir.exists() or out_dir.is_symlink():
            if out_dir.is_symlink():
                raise ContractError("materialization-output-symlink")
            shutil.rmtree(out_dir)
        os.replace(staging, out_dir)
        return receipt
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def check_materialized(fixture_dir: Path, out_dir: Path) -> dict[str, Any]:
    fixture = load_fixture(fixture_dir.resolve())
    output_path = out_dir.resolve() / OUTPUT_FILE
    receipt_path = out_dir.resolve() / RECEIPT_FILE
    if not output_path.is_file() or output_path.is_symlink():
        raise ContractError("materialization-output-missing")
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ContractError("materialization-receipt-missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    validate_receipt(receipt, output_path.read_bytes(), fixture)
    validate_fixture(fixture.manifest, output_path.read_bytes())
    return receipt
