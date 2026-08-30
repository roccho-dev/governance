from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROW_FIELDS = {
    "kind",
    "obligation_id",
    "adrs_ref",
    "target_universe_id",
    "repo_locator",
    "authority_surface",
    "package_id",
    "package_path",
    "owner_role",
    "goals",
    "non_goals",
    "requirements",
    "required_tests",
    "claim_required",
    "receipt_required",
    "residual_required",
    "freshness_policy",
    "route_policy",
    "authority",
}
MANIFEST_FIELDS = {
    "kind",
    "fixture_id",
    "source_file",
    "source_sha256",
    "row_count",
    "target_repository",
    "target_commit",
    "target_tree",
    "target_system",
    "inventory_algorithm",
    "active_package_ids",
    "inventory_inputs",
    "authority",
    "accepted_meaning_authority",
    "production_gate",
    "boundary",
}
PACKAGE_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class Fixture:
    manifest: dict[str, Any]
    rows: tuple[dict[str, Any], ...]
    source_bytes: bytes


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _require_exact_fields(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ContractError(f"{label}-fields:missing={missing}:extra={extra}")


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label}-string-required")
    return value


def _require_string_list(value: Any, label: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContractError(f"{label}-string-array-required")
    if not allow_empty and not value:
        raise ContractError(f"{label}-nonempty-required")
    if len(set(value)) != len(value):
        raise ContractError(f"{label}-duplicate")
    return value


def validate_row(row: dict[str, Any]) -> None:
    if not isinstance(row, dict):
        raise ContractError("row-object-required")
    _require_exact_fields(row, ROW_FIELDS, "row")
    if row["kind"] != "packageObligation.v1":
        raise ContractError("row-kind")
    package_id = _require_string(row["package_id"], "package-id")
    if not PACKAGE_ID_RE.fullmatch(package_id):
        raise ContractError(f"package-id-invalid:{package_id}")
    package_path = _require_string(row["package_path"], f"package-path:{package_id}")
    if package_path.startswith("/") or ".." in package_path.split("/"):
        raise ContractError(f"package-path-invalid:{package_id}")
    for field in (
        "obligation_id",
        "adrs_ref",
        "target_universe_id",
        "repo_locator",
        "authority_surface",
        "owner_role",
        "freshness_policy",
        "route_policy",
    ):
        _require_string(row[field], f"{field}:{package_id}")
    _require_string_list(row["goals"], f"goals:{package_id}", allow_empty=False)
    _require_string_list(row["non_goals"], f"non-goals:{package_id}", allow_empty=False)
    _require_string_list(row["requirements"], f"requirements:{package_id}", allow_empty=False)
    tests = _require_string_list(row["required_tests"], f"required-tests:{package_id}")
    for field in ("claim_required", "receipt_required", "residual_required", "authority"):
        if not isinstance(row[field], bool):
            raise ContractError(f"{field}-boolean-required:{package_id}")
    if row["authority"] is not False:
        raise ContractError(f"authority-must-be-false:{package_id}")
    if row["repo_locator"] != "roccho-dev/ops":
        raise ContractError(f"repo-locator-invalid:{package_id}")
    if row["claim_required"] and not tests:
        raise ContractError(f"active-package-test-required:{package_id}")
    if not row["claim_required"] and tests:
        raise ContractError(f"inactive-package-test-forbidden:{package_id}")
    if row["claim_required"] and row["residual_required"] is not True:
        raise ContractError(f"active-package-residual-required:{package_id}")


def parse_canonical_jsonl(source_bytes: bytes) -> list[dict[str, Any]]:
    if not source_bytes.endswith(b"\n"):
        raise ContractError("source-final-newline-required")
    if b"\r" in source_bytes:
        raise ContractError("source-cr-forbidden")
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(source_bytes.splitlines(), start=1):
        if not raw:
            raise ContractError(f"source-blank-line:{index}")
        try:
            text = raw.decode("utf-8")
            row = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractError(f"source-json:{index}:{exc}") from exc
        if not isinstance(row, dict):
            raise ContractError(f"source-object-required:{index}")
        if text != canonical_json(row):
            raise ContractError(f"source-noncanonical:{index}")
        validate_row(row)
        rows.append(row)
    return rows


def validate_fixture(manifest: dict[str, Any], source_bytes: bytes) -> Fixture:
    if not isinstance(manifest, dict):
        raise ContractError("manifest-object-required")
    _require_exact_fields(manifest, MANIFEST_FIELDS, "manifest")
    if manifest["kind"] != "adrsPackageObligationFixtureManifest.v1":
        raise ContractError("manifest-kind")
    for field in ("fixture_id", "source_file", "target_repository", "target_system", "inventory_algorithm", "boundary"):
        _require_string(manifest[field], f"manifest-{field}")
    if manifest["source_file"] != "source.jsonl":
        raise ContractError("manifest-source-file")
    if not SHA256_RE.fullmatch(str(manifest["source_sha256"])):
        raise ContractError("manifest-source-sha256")
    if sha256_bytes(source_bytes) != manifest["source_sha256"]:
        raise ContractError("manifest-source-digest-mismatch")
    if manifest["target_repository"] != "roccho-dev/ops":
        raise ContractError("manifest-target-repository")
    if not GIT_SHA_RE.fullmatch(str(manifest["target_commit"])) or not GIT_SHA_RE.fullmatch(str(manifest["target_tree"])):
        raise ContractError("manifest-target-git-identity")
    if manifest["target_system"] != "x86_64-linux":
        raise ContractError("manifest-target-system")
    if not isinstance(manifest["row_count"], int) or manifest["row_count"] < 1:
        raise ContractError("manifest-row-count")
    active = _require_string_list(manifest["active_package_ids"], "manifest-active-packages", allow_empty=False)
    if active != sorted(active):
        raise ContractError("manifest-active-packages-order")
    inputs = manifest["inventory_inputs"]
    if not isinstance(inputs, list) or not inputs:
        raise ContractError("manifest-inventory-inputs")
    for item in inputs:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ContractError("manifest-inventory-input-shape")
        _require_string(item["path"], "manifest-inventory-input-path")
        if not SHA256_RE.fullmatch(str(item["sha256"])):
            raise ContractError("manifest-inventory-input-digest")
    if len({item["path"] for item in inputs}) != len(inputs):
        raise ContractError("manifest-inventory-input-duplicate")
    if manifest["authority"] is not False or manifest["accepted_meaning_authority"] is not False or manifest["production_gate"] is not False:
        raise ContractError("manifest-authority-boundary")

    rows = parse_canonical_jsonl(source_bytes)
    if len(rows) != manifest["row_count"]:
        raise ContractError("manifest-row-count-mismatch")
    package_ids = [row["package_id"] for row in rows]
    obligation_ids = [row["obligation_id"] for row in rows]
    if package_ids != sorted(package_ids):
        raise ContractError("source-package-order")
    if len(set(package_ids)) != len(package_ids):
        raise ContractError("source-package-duplicate")
    if len(set(obligation_ids)) != len(obligation_ids):
        raise ContractError("source-obligation-duplicate")
    actual_active = sorted(row["package_id"] for row in rows if row["claim_required"])
    if actual_active != active:
        raise ContractError("manifest-active-package-drift")
    target_universe = f"roccho-dev/ops@{manifest['target_commit']}"
    for row in rows:
        if row["target_universe_id"] != target_universe:
            raise ContractError(f"target-universe-drift:{row['package_id']}")
    return Fixture(manifest=manifest, rows=tuple(rows), source_bytes=source_bytes)


def load_fixture(root: Path) -> Fixture:
    manifest_path = root / "manifest.json"
    source_path = root / "source.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return validate_fixture(manifest, source_path.read_bytes())


def canonical_source(rows: Iterable[dict[str, Any]]) -> bytes:
    values = list(rows)
    for row in values:
        validate_row(row)
    values.sort(key=lambda row: row["package_id"])
    return ("".join(canonical_json(row) + "\n" for row in values)).encode("utf-8")
