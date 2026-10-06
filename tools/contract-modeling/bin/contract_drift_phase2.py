#!/usr/bin/env python3
"""Thin Phase 2 composition around the exact ops contract-diff primitive.

ADRS owns meaning. This adapter validates already admitted A/S/U-shaped inputs,
builds the finite inventory, and invokes the one ops comparator implementation.
The existing governance compiler/gate alone owns provenance admission, final
grade, residuals, and closure receipt. This module contains no
supply/contract/evidence comparison algorithm and performs no
network, provider, credential, clock, latest, or effect operation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

MAX_BYTES = 2 * 1024 * 1024
HEX40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,255}$")
COLLECTIONS = ("required", "provided", "observations", "receipts")
SEALED_234_SEED = "contract_modeling/v1/source-seed.jsonl"


class ClosureError(ValueError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def object_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ClosureError("duplicate-property")
        out[key] = value
    return out


def load_json(path: Path) -> Any:
    if path.is_symlink():
        raise ClosureError("symlink-input")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ClosureError("input-too-large")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ClosureError("nonfinite-number")),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ClosureError("invalid-json") from exc


def closed(value: Any, required: tuple[str, ...], optional: tuple[str, ...] = ()) -> None:
    if not isinstance(value, dict):
        raise ClosureError("object-required")
    keys = set(value)
    if not set(required) <= keys <= set(required) | set(optional):
        raise ClosureError("closed-schema-required")


def token(value: Any) -> None:
    if not isinstance(value, str) or not TOKEN.fullmatch(value):
        raise ClosureError("invalid-identifier")


def source(value: Any) -> None:
    closed(value, ("repository", "revision", "path", "digest"))
    token(value["repository"])
    token(value["path"])
    if not HEX40.fullmatch(str(value["revision"])) or not DIGEST.fullmatch(str(value["digest"])):
        raise ClosureError("invalid-source-identity")
    # Reject aliases before exact authority-path comparison; never normalize silently.
    if any(part in {"", ".", ".."} for part in value["path"].split("/")):
        raise ClosureError("source-path-not-canonical")


def row_digest(rows: list[dict[str, Any]]) -> str:
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ClosureError("row-limit-or-schema")
    identities = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ClosureError("row-id-required")
        token(row["id"])
        identities.append(row["id"])
    if len(set(identities)) != len(identities):
        raise ClosureError("duplicate-row-id")
    return digest(sorted(rows, key=lambda row: row["id"]))


def validate_authority(value: Any) -> None:
    closed(value, ("kind", "source", "scope", "obligations", "evidence"))
    if value["kind"] != "governance.contractDriftAuthorityProjection.v1":
        raise ClosureError("authority-kind")
    source(value["source"])
    if value["source"]["path"] == SEALED_234_SEED:
        raise ClosureError("sealed-234-seed-is-not-contract-drift-authority")
    scope = value["scope"]
    closed(scope, ("id", "epoch", "allow_empty", "excluded_ids"))
    token(scope["id"])
    token(scope["epoch"])
    if type(scope["allow_empty"]) is not bool or not isinstance(scope["excluded_ids"], list):
        raise ClosureError("scope-schema")
    for identity in scope["excluded_ids"]:
        token(identity)
    if len(set(scope["excluded_ids"])) != len(scope["excluded_ids"]):
        raise ClosureError("duplicate-exclusion")
    if not isinstance(value["obligations"], list) or len(value["obligations"]) > 10000:
        raise ClosureError("obligation-schema")
    seen = set()
    for row in value["obligations"]:
        closed(row, ("id", "obligation_digest", "profile"))
        token(row["id"])
        if row["id"] in seen:
            raise ClosureError("duplicate-obligation")
        seen.add(row["id"])
        if not DIGEST.fullmatch(str(row["obligation_digest"])) or not isinstance(row["profile"], list):
            raise ClosureError("obligation-schema")
    if not isinstance(value["evidence"], dict):
        raise ClosureError("evidence-schema")
    for ref, value_digest in value["evidence"].items():
        token(ref)
        if not DIGEST.fullmatch(str(value_digest)):
            raise ClosureError("evidence-schema")


def validate_export(value: Any) -> None:
    closed(value, ("source", "rows"))
    source(value["source"])
    row_digest(value["rows"])


def comparator_identity(ops_root: Path, ops_revision: str) -> dict[str, Any]:
    if not HEX40.fullmatch(ops_revision):
        raise ClosureError("ops-revision-must-be-exact")
    root = ops_root.resolve()
    core = root / "core.py"
    cli = root / "bin" / "contract-diff.py"
    for path in (core, cli):
        if not path.is_file() or path.is_symlink():
            raise ClosureError("ops-comparator-source-missing")
    identity = {
        "repository": "roccho-dev/ops",
        "revision": ops_revision,
        "path": "packages/contract-diff",
        "core_digest": bytes_digest(core.read_bytes()),
        "cli_digest": bytes_digest(cli.read_bytes()),
    }
    identity["source_digest"] = digest(identity)
    return identity


def invoke_diff(
    ops_root: Path,
    packet: dict[str, Any],
    admission: dict[str, Any],
) -> dict[str, Any]:
    cli = ops_root.resolve() / "bin" / "contract-diff.py"
    with tempfile.TemporaryDirectory(prefix="governance-contract-drift-") as raw:
        root = Path(raw)
        packet_path, admission_path = root / "packet.json", root / "admission.json"
        packet_path.write_bytes(canonical(packet))
        admission_path.write_bytes(canonical(admission))
        result = subprocess.run(
            [sys.executable, str(cli), "--input", str(packet_path), "--admission", str(admission_path)],
            cwd=root,
            env={},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    if result.returncode not in {0, 2, 3, 4} or result.stderr:
        raise ClosureError("ops-comparator-execution-failed")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ClosureError("ops-comparator-output-invalid") from exc
    if not isinstance(value, dict) or value.get("kind") != "contractDiffResult.v1" or value.get("authority") is not False:
        raise ClosureError("ops-comparator-output-contract")
    return value


def compose(
    authority: dict[str, Any],
    exports: dict[str, dict[str, Any]],
    ops_root: Path,
    ops_revision: str,
    authority_grade: str,
) -> dict[str, Any]:
    if authority_grade not in {"fixture", "source"}:
        raise ClosureError("authority-grade")
    validate_authority(authority)
    if set(exports) != set(COLLECTIONS):
        raise ClosureError("collection-set")
    for value in exports.values():
        validate_export(value)
    scope = authority["scope"]
    packet = {"kind": "contractDiffInput.v1", **exports}
    inventory = {
        key: {
            "source": exports[key]["source"],
            "rows_digest": row_digest(exports[key]["rows"]),
            "count": len(exports[key]["rows"]),
        }
        for key in COLLECTIONS
    }
    admission = {
        "kind": "contractDiffAdmission.v1",
        "scope": {
            "id": scope["id"],
            "authority": authority["source"],
            "epoch": scope["epoch"],
            "allow_empty": scope["allow_empty"],
            "grade": authority_grade,
            "excluded_ids": scope["excluded_ids"],
        },
        "universe": authority["obligations"],
        "inventory": inventory,
        "evidence": authority["evidence"],
    }
    comparator = comparator_identity(ops_root, ops_revision)
    diff = invoke_diff(ops_root, packet, admission)
    return {
        "kind": "governance.contractDriftClosure.v1",
        "authority": False,
        "phase": "phase2",
        "scope": scope["id"],
        "input_grade": authority_grade,
        "status": diff["status"],
        "final_admission": False,
        "claim_ceiling": "candidate-diff-only; existing governance gate must admit authority and final closure",
        "authority_source": authority["source"],
        "comparator": comparator,
        "diff": diff,
    }



SELECTED_BINDING = "jev-api"
SELECTED_CONSUMER_BOUNDARY = "ops.voice-ui.consumer"
SELECTED_SCOPE_ID = "ops-envs.voice-ui-jev-api"
SELECTED_EPOCH = "canonical-source-v1"
OPS_REQUIREMENT_PATH = "packages/voice-ui-target-runtime/modules/input-contracts.mjs"


def exact_revision(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise ClosureError(label)
    return value


def selected_obligation_id() -> str:
    value = digest({"binding": SELECTED_BINDING, "consumer_boundary": SELECTED_CONSUMER_BOUNDARY})
    return "contract-drift:" + value.removeprefix("sha256:")


def _run_json(argv: list[str], label: str, cwd: Path | None = None) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            env={},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise ClosureError(label) from exc
    if result.returncode != 0 or result.stderr or len(result.stdout.encode("utf-8")) > MAX_BYTES:
        raise ClosureError(label)
    try:
        value = json.loads(
            result.stdout,
            object_pairs_hook=object_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ClosureError(label)),
        )
    except json.JSONDecodeError as exc:
        raise ClosureError(label) from exc
    if not isinstance(value, dict):
        raise ClosureError(label)
    return value


def _ops_source_identity(ops_repo_root: Path, ops_revision: str) -> dict[str, Any]:
    revision = exact_revision(ops_revision, "ops-revision-must-be-exact")
    module = ops_repo_root.resolve() / OPS_REQUIREMENT_PATH
    if not module.is_file() or module.is_symlink():
        raise ClosureError("ops-requirement-source-missing")
    return {
        "repository": "roccho-dev/ops",
        "revision": revision,
        "path": OPS_REQUIREMENT_PATH,
        "digest": bytes_digest(module.read_bytes()),
    }


def _project_ops_once(
    ops_repo_root: Path,
    node: Path,
    target: dict[str, Any],
    obligation_digest: str,
    ops_revision: str,
) -> dict[str, Any]:
    expected_source = _ops_source_identity(ops_repo_root, ops_revision)
    if not node.is_file():
        raise ClosureError("node-executable-missing")
    request = {
        "target": target,
        "obligation": {
            "id": selected_obligation_id(),
            "obligation_digest": obligation_digest,
            "binding": SELECTED_BINDING,
        },
    }
    helper_text = """import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const [modulePath, requestPath, revision] = process.argv.slice(2);
const { projectRequirements } = await import(pathToFileURL(modulePath).href);
const request = JSON.parse(readFileSync(requestPath, "utf8"));
process.stdout.write(JSON.stringify(projectRequirements(request.target, request.obligation, revision)));
"""
    with tempfile.TemporaryDirectory(prefix="governance-contract-drift-ops-") as raw:
        root = Path(raw)
        request_path = root / "request.json"
        helper = root / "project.mjs"
        request_path.write_bytes(canonical(request))
        helper.write_text(helper_text, encoding="utf-8")
        value = _run_json(
            [
                str(node),
                str(helper),
                str(ops_repo_root.resolve() / OPS_REQUIREMENT_PATH),
                str(request_path),
                ops_revision,
            ],
            "ops-requirement-acquisition-failed",
            root,
        )
    validate_export(value)
    if value["source"] != expected_source or len(value["rows"]) != 1:
        raise ClosureError("ops-requirement-source-identity")
    if value["rows"][0].get("id") != selected_obligation_id():
        raise ClosureError("ops-requirement-obligation-id")
    return value


def derive_required(
    ops_repo_root: Path,
    node: Path,
    target: dict[str, Any],
    ops_revision: str,
) -> dict[str, Any]:
    placeholder = "sha256:" + ("0" * 64)
    first = _project_ops_once(ops_repo_root, node, target, placeholder, ops_revision)
    contract = json.loads(json.dumps(first["rows"][0]["contract"]))
    if contract.pop("obligation_digest", None) != placeholder:
        raise ClosureError("ops-placeholder-digest-not-preserved")
    meaning = digest(contract)
    required = _project_ops_once(ops_repo_root, node, target, meaning, ops_revision)
    final_contract = json.loads(json.dumps(required["rows"][0]["contract"]))
    if final_contract.pop("obligation_digest", None) != meaning or final_contract != contract:
        raise ClosureError("ops-semantic-projection-not-deterministic")
    return required


def _project_envs(
    envs_root: Path,
    selector: dict[str, Any] | None,
    envs_revision: str,
) -> dict[str, Any]:
    revision = exact_revision(envs_revision, "envs-revision-must-be-exact")
    root = envs_root.resolve()
    adapter = root / "adapters" / "contract_projection.py"
    if not adapter.is_file() or adapter.is_symlink():
        raise ClosureError("envs-projection-source-missing")
    selection = {"obligations": [] if selector is None else [selector]}
    with tempfile.TemporaryDirectory(prefix="governance-contract-drift-envs-") as raw:
        selection_path = Path(raw) / "selection.json"
        selection_path.write_bytes(canonical(selection))
        value = _run_json(
            [
                sys.executable,
                str(adapter),
                "--root",
                str(root),
                "--selection",
                str(selection_path),
                "--revision",
                revision,
            ],
            "envs-provision-acquisition-failed",
            root,
        )
    validate_export(value)
    return value


def _envs_source_identity(envs_root: Path, envs_revision: str) -> dict[str, Any]:
    value = _project_envs(envs_root, None, envs_revision)
    if value["rows"]:
        raise ClosureError("empty-envs-source-projection-produced-rows")
    return value["source"]


def validate_acquired_sources(
    required: dict[str, Any],
    provided: dict[str, Any],
    ops_repo_root: Path,
    envs_root: Path,
    ops_revision: str,
    envs_revision: str,
) -> None:
    validate_export(required)
    validate_export(provided)
    if required["source"] != _ops_source_identity(ops_repo_root, ops_revision):
        raise ClosureError("ops-acquisition-source-mismatch")
    if provided["source"] != _envs_source_identity(envs_root, envs_revision):
        raise ClosureError("envs-acquisition-source-mismatch")


def _selector(required: dict[str, Any]) -> dict[str, Any]:
    if len(required["rows"]) != 1:
        raise ClosureError("required-row-cardinality")
    row = required["rows"][0]
    contract = row.get("contract")
    if not isinstance(contract, dict):
        raise ClosureError("required-contract-shape")
    meaning = contract.get("obligation_digest")
    profile = contract.get("profile")
    if not isinstance(meaning, str) or not DIGEST.fullmatch(meaning) or not isinstance(profile, list):
        raise ClosureError("required-contract-meaning")
    return {
        "id": selected_obligation_id(),
        "obligation_digest": meaning,
        "binding": SELECTED_BINDING,
        "consumer_boundary": SELECTED_CONSUMER_BOUNDARY,
        "profile": profile,
    }


def _authority_from_required(required: dict[str, Any]) -> dict[str, Any]:
    selector = _selector(required)
    return {
        "kind": "governance.contractDriftAuthorityProjection.v1",
        "source": required["source"],
        "scope": {
            "id": SELECTED_SCOPE_ID,
            "epoch": SELECTED_EPOCH,
            "allow_empty": False,
            "excluded_ids": [],
        },
        "obligations": [{
            "id": selector["id"],
            "obligation_digest": selector["obligation_digest"],
            "profile": selector["profile"],
        }],
        "evidence": {},
    }


def _empty_export(source_value: dict[str, Any]) -> dict[str, Any]:
    return {"source": json.loads(json.dumps(source_value)), "rows": []}


def acquire_bounded(
    ops_repo_root: Path,
    envs_root: Path,
    node: Path,
    ops_revision: str,
    envs_revision: str,
    target: dict[str, Any] | None,
) -> dict[str, Any]:
    exact_revision(ops_revision, "ops-revision-must-be-exact")
    exact_revision(envs_revision, "envs-revision-must-be-exact")
    sources = {
        "ops": _ops_source_identity(ops_repo_root, ops_revision),
        "envs": _envs_source_identity(envs_root, envs_revision),
    }
    if target is None:
        return {
            "kind": "governance.contractDriftAcquisition.v1",
            "authority": False,
            "status": "UNKNOWN",
            "reason": "target-input-unavailable",
            "sources": sources,
            "selector": {
                "binding": SELECTED_BINDING,
                "consumer_boundary": SELECTED_CONSUMER_BOUNDARY,
                "id": selected_obligation_id(),
            },
            "provider_effect": False,
            "final_admission": False,
        }

    required = derive_required(ops_repo_root, node, target, ops_revision)
    selector = _selector(required)
    provided = _project_envs(envs_root, selector, envs_revision)
    validate_acquired_sources(required, provided, ops_repo_root, envs_root, ops_revision, envs_revision)
    authority = _authority_from_required(required)
    exports = {
        "required": required,
        "provided": provided,
        # This slice inventories canonical public source only. Real O/H remains
        # a separate input/effect boundary and is never inferred from file presence.
        "observations": _empty_export(required["source"]),
        "receipts": _empty_export(provided["source"]),
    }
    closure = compose(
        authority,
        exports,
        ops_repo_root.resolve() / "packages" / "contract-diff",
        ops_revision,
        "source",
    )
    return {
        "kind": "governance.contractDriftAcquisition.v1",
        "authority": False,
        "status": closure["status"],
        "sources": {"ops": required["source"], "envs": provided["source"]},
        "selector": selector,
        "evidence_boundary": "canonical-public-source-only; real provider observations/receipts are separate",
        "normalized": {"authority": authority, **exports},
        "closure": closure,
        "provider_effect": False,
        "final_admission": False,
    }


def _finding(result: dict[str, Any], kind: str, field: str | None = None) -> bool:
    findings = result.get("diff", {}).get("findings", [])
    return any(
        item.get("kind") == kind and (field is None or item.get("field") == field)
        for item in findings
        if isinstance(item, dict)
    )


def _synthetic_envs_projection(
    envs_root: Path,
    selector: dict[str, Any],
    mutate,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="governance-contract-drift-envs-synthetic-") as raw:
        root = Path(raw)
        (root / "adapters").mkdir()
        (root / "contracts").mkdir()
        (root / "adapters" / "contract_projection.py").write_bytes(
            (envs_root.resolve() / "adapters" / "contract_projection.py").read_bytes()
        )
        bindings_path = envs_root.resolve() / "contracts" / "bindings.jsonl"
        consumers_path = envs_root.resolve() / "contracts" / "provider-consumer.jsonl"
        bindings = [json.loads(line) for line in bindings_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        consumers = [json.loads(line) for line in consumers_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        mutate(bindings, consumers)
        (root / "contracts" / "bindings.jsonl").write_bytes(
            b"\n".join(canonical(row) for row in bindings) + b"\n"
        )
        (root / "contracts" / "provider-consumer.jsonl").write_bytes(
            b"\n".join(canonical(row) for row in consumers) + b"\n"
        )
        return _project_envs(root, selector, "b" * 40)


def acquisition_selftest(
    ops_repo_root: Path,
    envs_root: Path,
    node: Path,
    ops_revision: str,
    envs_revision: str,
) -> int:
    target = {
        "provider": "cloudflare-workers",
        "accountId": "0" * 32,
        "workerName": "voice-ui-fixture",
        "url": "https://voice-ui-fixture.fixture.workers.dev/",
        "nativeDeploySettings": {
            "workersDev": True,
            "previewUrls": False,
            "observability": {"enabled": False},
            "tags": [],
        },
    }
    result = acquire_bounded(ops_repo_root, envs_root, node, ops_revision, envs_revision, target)
    if result["sources"]["ops"]["revision"] != ops_revision or result["sources"]["envs"]["revision"] != envs_revision:
        raise ClosureError("canonical-merge-provenance-not-retained")
    cases = ["canonical-merge-provenance-retained"]

    normalized = result["normalized"]
    authority = normalized["authority"]
    exports = {name: normalized[name] for name in COLLECTIONS}
    if not _finding(result["closure"], "CONTRACT_DRIFT", "target"):
        raise ClosureError("canonical-workers-pages-drift-missing")
    if not _finding(result["closure"], "EVIDENCE_MISSING"):
        raise ClosureError("canonical-required-evidence-missing-not-detected")
    if exports["required"]["rows"][0]["id"] != exports["provided"]["rows"][0]["id"]:
        raise ClosureError("stable-k-not-preserved")
    cases.extend(["workers-pages-target-drift", "required-evidence-missing", "stable-k-across-r-p"])

    missing_r = json.loads(json.dumps(exports))
    missing_r["required"]["rows"] = []
    missing_r_result = compose(
        authority,
        missing_r,
        ops_repo_root.resolve() / "packages" / "contract-diff",
        ops_revision,
        "source",
    )
    if missing_r_result["status"] == "CLOSED" or not _finding(missing_r_result, "COVERAGE_GAP"):
        raise ClosureError("missing-r-vacuous-pass")
    cases.append("selected-relation-missing-r-is-not-vacuous")

    def stage_drift(bindings, consumers):
        next(row for row in consumers if row["id"] == SELECTED_CONSUMER_BOUNDARY)["stage"] = "stage-drift"

    def consumer_drift(bindings, consumers):
        next(row for row in consumers if row["id"] == SELECTED_CONSUMER_BOUNDARY)["repository"] = "roccho-dev/ops-drift"

    def capability_drift(bindings, consumers):
        next(row for row in bindings if row["id"] == SELECTED_BINDING)["capability"] = "jev-api-drift"
        next(row for row in consumers if row["id"] == SELECTED_CONSUMER_BOUNDARY)["capability"] = "jev-api-drift"

    for label, field, mutate in (
        ("stage", "stage", stage_drift),
        ("consumer", "consumer", consumer_drift),
        ("capability", "capability", capability_drift),
    ):
        synthetic = _synthetic_envs_projection(envs_root, result["selector"], mutate)
        changed = json.loads(json.dumps(exports))
        changed["provided"] = synthetic
        compared = compose(
            authority,
            changed,
            ops_repo_root.resolve() / "packages" / "contract-diff",
            ops_revision,
            "source",
        )
        if not _finding(compared, "CONTRACT_DRIFT", field):
            raise ClosureError("compared-field-drift-not-preserved")
        if any(item.get("kind", "").startswith("SUPPLY_") for item in compared["diff"].get("findings", [])):
            raise ClosureError("compared-field-drift-became-supply")
        if synthetic["rows"][0]["id"] != selected_obligation_id():
            raise ClosureError("synthetic-stable-k-changed")
        cases.append(f"{label}-drift-same-k")

    def relation_missing(bindings, consumers):
        consumers[:] = [row for row in consumers if row["id"] != SELECTED_CONSUMER_BOUNDARY]

    absent = _synthetic_envs_projection(envs_root, result["selector"], relation_missing)
    missing_p = json.loads(json.dumps(exports))
    missing_p["provided"] = absent
    missing_p_result = compose(
        authority,
        missing_p,
        ops_repo_root.resolve() / "packages" / "contract-diff",
        ops_revision,
        "source",
    )
    if not _finding(missing_p_result, "SUPPLY_MISSING"):
        raise ClosureError("true-relation-absence-not-supply-missing")
    cases.append("stable-relation-absence-is-supply-missing")

    unknown = acquire_bounded(ops_repo_root, envs_root, node, ops_revision, envs_revision, None)
    if unknown["status"] != "UNKNOWN" or unknown["reason"] != "target-input-unavailable":
        raise ClosureError("missing-target-not-unknown")
    cases.append("missing-target-is-unknown")

    tampered_required = json.loads(json.dumps(exports["required"]))
    tampered_required["source"]["digest"] = "sha256:" + ("f" * 64)
    try:
        validate_acquired_sources(
            tampered_required,
            exports["provided"],
            ops_repo_root,
            envs_root,
            ops_revision,
            envs_revision,
        )
    except ClosureError as exc:
        if str(exc) != "ops-acquisition-source-mismatch":
            raise
    else:
        raise ClosureError("source-identity-mismatch-admitted")
    cases.append("source-identity-mismatch-rejected")

    if result["closure"]["final_admission"] is not False or result["final_admission"] is not False:
        raise ClosureError("acquisition-self-promoted")
    cases.append("acquisition-never-final-admission")

    again = acquire_bounded(ops_repo_root, envs_root, node, ops_revision, envs_revision, target)
    if canonical(result) != canonical(again):
        raise ClosureError("acquisition-not-deterministic")
    cases.append("same-exact-input-byte-identical")

    if "roccho-dev/adrs" in canonical(result).decode("utf-8") or "contract-drift/authority-source" in canonical(result).decode("utf-8"):
        raise ClosureError("new-adrs-source-became-required-input")
    cases.append("no-new-adrs-cue-adoption-input")

    report = {
        "kind": "governance.contractDriftAcquisition.selftest.v1",
        "status": "pass",
        "authority": False,
        "fixture_target_only": True,
        "canonical_sources": {
            "ops": result["sources"]["ops"],
            "envs": result["sources"]["envs"],
        },
        "case_count": len(cases),
        "cases": cases,
        "provider_effect": False,
        "final_admission_claimed": False,
    }
    sys.stdout.buffer.write(canonical(report) + b"\n")
    return 0

def fixture_source(label: str, repository: str = "fixture/repo") -> dict[str, Any]:
    return {
        "repository": repository,
        "revision": "a" * 40,
        "path": label + ".json",
        "digest": digest(label),
    }


def selftest(ops_root: Path, ops_revision: str) -> int:
    profile: list[dict[str, Any]] = []
    semantic = digest("accepted-contract-meaning")
    obligation = {"id": "fixture.contract-drift", "obligation_digest": semantic, "profile": profile}
    workers = {
        "obligation_digest": semantic,
        "capability": "jev-api",
        "consumer": "roccho-dev/ops",
        "stage": "dev",
        "target": {"provider": "cloudflare-workers", "resource": "voice-ui", "account": None},
        "slot": "JEV_API_KEY",
        "binding": "jev-api",
        "profile": profile,
    }
    authority = {
        "kind": "governance.contractDriftAuthorityProjection.v1",
        "source": fixture_source("contract-drift-authority", "roccho-dev/adrs"),
        "scope": {"id": "fixture.contract-drift", "epoch": "fixture-epoch", "allow_empty": False, "excluded_ids": []},
        "obligations": [obligation],
        "evidence": {},
    }

    def export(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        repository = {"required": "roccho-dev/ops", "provided": "roccho-dev/envs"}.get(name, "fixture/evidence")
        return {"source": fixture_source(name, repository), "rows": rows}

    required_row = {"id": obligation["id"], "contract": workers}
    base = {
        "required": export("required", [required_row]),
        "provided": export("provided", [{"id": obligation["id"], "contract": dict(workers)}]),
        "observations": export("observations", []),
        "receipts": export("receipts", []),
    }
    cases = []

    closed_result = compose(authority, base, ops_root, ops_revision, "fixture")
    if closed_result["status"] != "CLOSED" or closed_result["final_admission"] is not False:
        raise ClosureError("fixture-closed-boundary")
    cases.append("fixture-closed-not-final-admission")

    # Even a caller-supplied source grade cannot self-promote the candidate to
    # final governance admission. The existing governance gate must admit it.
    source_labeled = compose(authority, base, ops_root, ops_revision, "source")
    if source_labeled["status"] != "CLOSED" or source_labeled["final_admission"] is not False:
        raise ClosureError("source-label-self-admitted")
    cases.append("source-label-does-not-grant-final-admission")

    v24 = {key: json.loads(json.dumps(value)) for key, value in base.items()}
    v24["required"]["rows"] = []
    result = compose(authority, v24, ops_root, ops_revision, "fixture")
    if result["status"] != "OPEN" or not any(
        finding.get("kind") == "COVERAGE_GAP" for finding in result["diff"].get("findings", [])
    ):
        raise ClosureError("v24-accepted-universe-missing-required")
    cases.append("v24-authority-universe-catches-missing-r")

    v25 = {key: json.loads(json.dumps(value)) for key, value in base.items()}
    orphan = json.loads(json.dumps(v25["provided"]["rows"][0]))
    orphan["id"] = "fixture.orphan"
    v25["provided"]["rows"].append(orphan)
    result = compose(authority, v25, ops_root, ops_revision, "fixture")
    if result["status"] != "INVALID":
        raise ClosureError("v25-orphan-projection")
    cases.append("v25-orphan-rejected")

    v26 = {key: json.loads(json.dumps(value)) for key, value in base.items()}
    v26["provided"]["rows"][0]["contract"]["target"] = {
        "provider": "cloudflare-pages", "resource": "voice-ui", "account": None
    }
    result = compose(authority, v26, ops_root, ops_revision, "fixture")
    if result["status"] != "OPEN" or not any(
        finding.get("kind") == "CONTRACT_DRIFT" and finding.get("field") == "target"
        for finding in result["diff"].get("findings", [])
    ):
        raise ClosureError("v26-typed-drift")
    cases.append("v26-typed-drift-from-ops-primitive")

    evidence_authority = json.loads(json.dumps(authority))
    evidence_profile = [{"role": "projection", "operation": "cloudflare_workers_secret_put", "readback": True, "grade": "fixture"}]
    evidence_authority["obligations"][0]["profile"] = evidence_profile
    evidence_exports = {key: json.loads(json.dumps(value)) for key, value in base.items()}
    for key in ("required", "provided"):
        evidence_exports[key]["rows"][0]["contract"]["profile"] = evidence_profile
    result = compose(evidence_authority, evidence_exports, ops_root, ops_revision, "fixture")
    if result["status"] != "OPEN" or not any(
        finding.get("kind") == "EVIDENCE_MISSING" for finding in result["diff"].get("findings", [])
    ):
        raise ClosureError("v26-evidence-edge")
    cases.append("v26-evidence-edge-typed")

    identity = closed_result["comparator"]
    if identity["revision"] != ops_revision or identity["repository"] != "roccho-dev/ops":
        raise ClosureError("v27-comparator-pin")
    if not DIGEST.fullmatch(identity["source_digest"]):
        raise ClosureError("v27-comparator-source")
    cases.append("v27-one-exact-ops-comparator")

    for case, source_path, expected in (
        ("v28-sealed-seed-preserved", SEALED_234_SEED,
         "sealed-234-seed-is-not-contract-drift-authority"),
        ("v28-dot-alias-rejected", "contract_modeling/v1/./source-seed.jsonl",
         "source-path-not-canonical"),
        ("v28-empty-segment-rejected", "contract_modeling//v1/source-seed.jsonl",
         "source-path-not-canonical"),
        ("v28-trailing-separator-rejected", SEALED_234_SEED + "/",
         "source-path-not-canonical"),
        ("v28-parent-segment-rejected", "contract_modeling/v1/../v1/source-seed.jsonl",
         "source-path-not-canonical"),
        ("v28-absolute-path-rejected", "/" + SEALED_234_SEED,
         "invalid-identifier"),
    ):
        sealed = json.loads(json.dumps(authority))
        sealed["source"]["path"] = source_path
        try:
            compose(sealed, base, ops_root, ops_revision, "fixture")
        except ClosureError as exc:
            if str(exc) != expected:
                raise
        else:
            raise ClosureError("v28-sealed-seed-accepted")
        cases.append(case)

    # A valid nested path is not confused with the sealed seed or its aliases.
    nested = json.loads(json.dumps(authority))
    nested["source"]["path"] = "contract_modeling/v2/contract-drift.json"
    if compose(nested, base, ops_root, ops_revision, "fixture")["status"] != "CLOSED":
        raise ClosureError("v28-canonical-path-rejected")
    cases.append("v28-canonical-nested-path-accepted")

    first = canonical(compose(authority, base, ops_root, ops_revision, "fixture"))
    second = canonical(compose(authority, base, ops_root, ops_revision, "fixture"))
    if first != second:
        raise ClosureError("determinism")
    cases.append("deterministic-replay")

    report = {
        "kind": "governance.contractDriftPhase2.selftest.v1",
        "status": "pass",
        "authority": False,
        "fixture_only": True,
        "case_count": len(cases),
        "cases": cases,
        "ops_comparator": comparator_identity(ops_root, ops_revision),
        "provider_effect": False,
        "accepted_540_authority_claimed": False,
        "final_admission_claimed": False,
    }
    sys.stdout.buffer.write(canonical(report) + b"\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    selftest_parser = sub.add_parser("selftest")
    selftest_parser.add_argument("--ops-root", type=Path, required=True)
    selftest_parser.add_argument("--ops-revision", required=True)

    acquisition_test = sub.add_parser("acquisition-selftest")
    acquisition_test.add_argument("--ops-root", type=Path, required=True)
    acquisition_test.add_argument("--envs-root", type=Path, required=True)
    acquisition_test.add_argument("--node", type=Path, required=True)
    acquisition_test.add_argument("--ops-revision", required=True)
    acquisition_test.add_argument("--envs-revision", required=True)

    acquire_parser = sub.add_parser("acquire")
    acquire_parser.add_argument("--ops-root", type=Path, required=True)
    acquire_parser.add_argument("--envs-root", type=Path, required=True)
    acquire_parser.add_argument("--node", type=Path, required=True)
    acquire_parser.add_argument("--ops-revision", required=True)
    acquire_parser.add_argument("--envs-revision", required=True)
    acquire_parser.add_argument("--target", type=Path)
    acquire_parser.add_argument("--out", type=Path, required=True)

    compose_parser = sub.add_parser("compose")
    compose_parser.add_argument("--authority", type=Path, required=True)
    for name in COLLECTIONS:
        compose_parser.add_argument("--" + name, type=Path, required=True)
    compose_parser.add_argument("--ops-root", type=Path, required=True)
    compose_parser.add_argument("--ops-revision", required=True)
    compose_parser.add_argument("--authority-grade", choices=["fixture", "source"], required=True)
    compose_parser.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "selftest":
            return selftest(args.ops_root, args.ops_revision)
        if args.command == "acquisition-selftest":
            return acquisition_selftest(
                args.ops_root, args.envs_root, args.node, args.ops_revision, args.envs_revision
            )
        if args.command == "acquire":
            target = load_json(args.target) if args.target else None
            result = acquire_bounded(
                args.ops_root, args.envs_root, args.node, args.ops_revision, args.envs_revision, target
            )
            args.out.write_bytes(canonical(result) + b"\n")
            sys.stdout.buffer.write(canonical(result) + b"\n")
            return 4 if result["status"] == "UNKNOWN" else 0
        authority = load_json(args.authority)
        exports = {name: load_json(getattr(args, name)) for name in COLLECTIONS}
        result = compose(authority, exports, args.ops_root, args.ops_revision, args.authority_grade)
        args.out.write_bytes(canonical(result) + b"\n")
        sys.stdout.buffer.write(canonical(result) + b"\n")
        return {"CLOSED": 0, "OPEN": 2, "INVALID": 3, "UNKNOWN": 4}[result["status"]]
    except (ClosureError, OSError, TypeError, KeyError, RecursionError) as exc:
        sys.stderr.write("contract-drift-phase2: invalid or unavailable admitted input\n")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
