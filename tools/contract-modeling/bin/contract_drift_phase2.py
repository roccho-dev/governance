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
OPS_CANONICAL_REVISION = "8c44728263a02c5d693d41078021af876420d4a4"
ENVS_CANONICAL_REVISION = "c1a7658f142c82af4ad5cdeba23ee893ef662868"
SELECTED_DEPLOY_REVISION = "bce3daab76c9a4565902205cc59bb443f6e68009"
APPROVED_TARGET_KIND = "governance.voiceUiApprovedTargetSelection.v1"


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


def _ops_expectation_spec(
    ops_repo_root: Path,
    node: Path,
    target: dict[str, Any],
) -> dict[str, Any]:
    if not node.is_file():
        raise ClosureError("node-executable-missing")
    module = ops_repo_root.resolve() / OPS_REQUIREMENT_PATH
    helper_text = """import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const [modulePath, targetPath] = process.argv.slice(2);
const { PROJECTION_REQUIREMENTS, validateWorkersTarget } = await import(pathToFileURL(modulePath).href);
const target = JSON.parse(readFileSync(targetPath, "utf8"));
process.stdout.write(JSON.stringify({requirements: PROJECTION_REQUIREMENTS, target: validateWorkersTarget(target)}));
"""
    with tempfile.TemporaryDirectory(prefix="governance-contract-drift-spec-") as raw:
        root = Path(raw)
        target_path = root / "target.json"
        helper = root / "spec.mjs"
        target_path.write_bytes(canonical(target))
        helper.write_text(helper_text, encoding="utf-8")
        value = _run_json(
            [str(node), str(helper), str(module), str(target_path)],
            "ops-target-contract-invalid-or-unavailable",
            root,
        )
    closed(value, ("requirements", "target"))
    requirements = value["requirements"]
    closed(
        requirements,
        ("kind", "stage", "capability", "provider", "slot", "sourceKind", "operation", "readbackKind"),
    )
    for item in requirements.values():
        token(item)
    if requirements["kind"] != "envs.projectionReceipt.v1":
        raise ClosureError("ops-requirement-kind")
    return value


def derive_expectation(
    ops_repo_root: Path,
    node: Path,
    target: dict[str, Any],
    ops_revision: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_identity = _ops_source_identity(ops_repo_root, ops_revision)
    spec = _ops_expectation_spec(ops_repo_root, node, target)
    requirements = spec["requirements"]
    selected_target = spec["target"]
    profile = [{
        "role": "projection",
        "operation": requirements["operation"],
        "readback": True,
        "grade": "real",
    }]
    semantic_contract = {
        "capability": requirements["capability"],
        "consumer": "roccho-dev/ops",
        "stage": requirements["stage"],
        "target": {
            "provider": requirements["provider"],
            "resource": selected_target["workerName"],
            "account": selected_target["accountId"],
        },
        "slot": requirements["slot"],
        "binding": SELECTED_BINDING,
        "profile": profile,
    }
    meaning = digest(semantic_contract)
    expected_contract = {"obligation_digest": meaning, **semantic_contract}
    selector = {
        "id": selected_obligation_id(),
        "obligation_digest": meaning,
        "binding": SELECTED_BINDING,
        "consumer_boundary": SELECTED_CONSUMER_BOUNDARY,
        "profile": profile,
    }
    authority = {
        "kind": "governance.contractDriftAuthorityProjection.v1",
        "source": source_identity,
        "scope": {
            "id": SELECTED_SCOPE_ID,
            "epoch": SELECTED_EPOCH,
            "allow_empty": False,
            "excluded_ids": [],
        },
        "obligations": [{
            "id": selector["id"],
            "obligation_digest": meaning,
            "profile": profile,
        }],
        "evidence": {},
    }
    validate_authority(authority)
    return authority, selector, expected_contract


def derive_required(
    ops_repo_root: Path,
    node: Path,
    target: dict[str, Any],
    ops_revision: str,
    expected_contract: dict[str, Any],
) -> dict[str, Any]:
    meaning = expected_contract["obligation_digest"]
    required = _project_ops_once(ops_repo_root, node, target, meaning, ops_revision)
    if required["rows"][0].get("contract") != expected_contract:
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


def _empty_export(source_value: dict[str, Any]) -> dict[str, Any]:
    return {"source": json.loads(json.dumps(source_value)), "rows": []}


def _approved_target_selection(
    path: Path | None,
    admitted_digest: str | None,
    envs_revision: str,
    selected_deploy_revision: str,
    ops_repo_root: Path,
    node: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if path is None:
        return None, {
            "kind": APPROVED_TARGET_KIND,
            "status": "UNKNOWN",
            "reason": "approved-target-unavailable",
            "selected_deploy_revision": selected_deploy_revision,
            "envs_revision": envs_revision,
        }
    if admitted_digest is None or not DIGEST.fullmatch(admitted_digest):
        raise ClosureError("approved-target-admission-digest-required")
    if path.is_symlink():
        raise ClosureError("approved-target-symlink")
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ClosureError("approved-target-too-large")
    if bytes_digest(raw) != admitted_digest:
        raise ClosureError("approved-target-admission-digest-mismatch")
    packet = load_json(path)
    closed(packet, (
        "kind", "selected_deploy_revision", "envs_revision",
        "source", "target_digest", "target",
    ))
    if packet["kind"] != APPROVED_TARGET_KIND:
        raise ClosureError("approved-target-kind")
    try:
        source(packet["source"])
    except InputError as exc:
        raise ClosureError("approved-target-source-identity") from exc
    if exact_revision(packet["selected_deploy_revision"], "approved-target-deploy-revision") != selected_deploy_revision:
        raise ClosureError("approved-target-selected-deploy-mismatch")
    if exact_revision(packet["envs_revision"], "approved-target-envs-revision") != envs_revision:
        raise ClosureError("approved-target-envs-revision-mismatch")
    spec = _ops_expectation_spec(ops_repo_root, node, packet["target"])
    target = spec["target"]
    if packet["target_digest"] != digest(target):
        raise ClosureError("approved-target-digest-mismatch")
    return target, {
        "kind": APPROVED_TARGET_KIND,
        "status": "ADMITTED_INPUT",
        "digest": admitted_digest,
        "selected_deploy_revision": selected_deploy_revision,
        "envs_revision": envs_revision,
        "source": packet["source"],
        "target_digest": packet["target_digest"],
    }


def _evidence_inputs(
    authority: dict[str, Any],
    required_source: dict[str, Any],
    provided_source: dict[str, Any],
    observations: dict[str, Any] | None,
    receipts: dict[str, Any] | None,
    evidence_admission: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str], str | None]:
    supplied = [observations is not None, receipts is not None, evidence_admission is not None]
    if any(supplied) and not all(supplied):
        return _empty_export(required_source), _empty_export(provided_source), {}, "evidence-input-incomplete"
    if not any(supplied):
        return _empty_export(required_source), _empty_export(provided_source), {}, None

    validate_export(observations)
    validate_export(receipts)
    if not isinstance(evidence_admission, dict):
        raise ClosureError("evidence-admission-object-required")
    trusted: dict[str, str] = {}
    for ref, value_digest in evidence_admission.items():
        token(ref)
        if not isinstance(value_digest, str) or not DIGEST.fullmatch(value_digest):
            raise ClosureError("evidence-admission-digest")
        trusted[ref] = value_digest

    receipt_rows = {row["id"]: row for row in receipts["rows"] if isinstance(row, dict) and isinstance(row.get("id"), str)}
    required_refs: set[str] = set()
    for row in observations["rows"]:
        if not isinstance(row, dict):
            raise ClosureError("observation-row-shape")
        refs = row.get("refs")
        if not isinstance(refs, dict):
            raise ClosureError("observation-refs-shape")
        for ref in refs.values():
            token(ref)
            required_refs.add(ref)
    if not required_refs <= set(trusted):
        return observations, receipts, trusted, "evidence-provenance-unadmitted"
    for ref in required_refs & set(receipt_rows):
        if trusted.get(ref) != digest(receipt_rows[ref]):
            return observations, receipts, trusted, "evidence-provenance-digest-mismatch"

    authority["evidence"] = trusted
    return observations, receipts, trusted, None


def acquire_bounded(
    ops_repo_root: Path,
    envs_root: Path,
    node: Path,
    ops_revision: str,
    envs_revision: str,
    target: dict[str, Any] | None,
    *,
    input_grade: str = "fixture",
    target_provenance: dict[str, Any] | None = None,
    observations: dict[str, Any] | None = None,
    receipts: dict[str, Any] | None = None,
    evidence_admission: dict[str, Any] | None = None,
    selected_deploy_revision: str | None = None,
) -> dict[str, Any]:
    exact_revision(ops_revision, "ops-revision-must-be-exact")
    exact_revision(envs_revision, "envs-revision-must-be-exact")
    if input_grade not in {"fixture", "source"}:
        raise ClosureError("acquisition-input-grade")
    if input_grade == "source":
        if ops_revision != OPS_CANONICAL_REVISION or envs_revision != ENVS_CANONICAL_REVISION:
            raise ClosureError("source-grade-canonical-revision-mismatch")
        if selected_deploy_revision != SELECTED_DEPLOY_REVISION:
            raise ClosureError("source-grade-selected-deploy-mismatch")
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
            "input_grade": input_grade,
            "target_provenance": target_provenance,
            "selected_deploy_revision": selected_deploy_revision,
            "provider_effect": False,
            "final_admission": False,
        }

    if input_grade == "source" and (not isinstance(target_provenance, dict) or target_provenance.get("status") != "ADMITTED_INPUT"):
        return {
            "kind": "governance.contractDriftAcquisition.v1",
            "authority": False,
            "status": "UNKNOWN",
            "reason": "approved-target-provenance-unavailable",
            "sources": sources,
            "input_grade": input_grade,
            "target_provenance": target_provenance,
            "selected_deploy_revision": selected_deploy_revision,
            "provider_effect": False,
            "final_admission": False,
        }

    # U/K/profile are fixed before attempting R acquisition so a missing/empty
    # requirement projection cannot erase the selected obligation.
    authority, selector, expected_contract = derive_expectation(
        ops_repo_root, node, target, ops_revision
    )
    provided = _project_envs(envs_root, selector, envs_revision)
    try:
        required = derive_required(
            ops_repo_root, node, target, ops_revision, expected_contract
        )
    except ClosureError:
        return {
            "kind": "governance.contractDriftAcquisition.v1",
            "authority": False,
            "status": "UNKNOWN",
            "reason": "required-acquisition-unavailable",
            "sources": sources,
            "selector": selector,
            "normalized": {
                "authority": authority,
                "required": _empty_export(sources["ops"]),
                "provided": provided,
            },
            "provider_effect": False,
            "final_admission": False,
        }
    validate_acquired_sources(required, provided, ops_repo_root, envs_root, ops_revision, envs_revision)
    normalized_observations, normalized_receipts, trusted_evidence, evidence_error = _evidence_inputs(
        authority,
        required["source"],
        provided["source"],
        observations,
        receipts,
        evidence_admission,
    )
    if evidence_error is not None:
        return {
            "kind": "governance.contractDriftAcquisition.v1",
            "authority": False,
            "status": "UNKNOWN",
            "reason": evidence_error,
            "sources": {"ops": required["source"], "envs": provided["source"]},
            "selector": selector,
            "input_grade": input_grade,
            "target_provenance": target_provenance,
            "selected_deploy_revision": selected_deploy_revision,
            "provider_effect": False,
            "final_admission": False,
        }
    exports = {
        "required": required,
        "provided": provided,
        "observations": normalized_observations,
        "receipts": normalized_receipts,
    }
    closure = compose(
        authority,
        exports,
        ops_repo_root.resolve() / "packages" / "contract-diff",
        ops_revision,
        input_grade,
    )
    return {
        "kind": "governance.contractDriftAcquisition.v1",
        "authority": False,
        "status": closure["status"],
        "sources": {"ops": required["source"], "envs": provided["source"]},
        "selector": selector,
        "input_grade": input_grade,
        "target_provenance": target_provenance,
        "selected_deploy_revision": selected_deploy_revision,
        "universe_derivation": "runtime-requirement-spec-plus-stable-selection-before-required-acquisition",
        "evidence_boundary": "already-produced observations/receipts are accepted only with closed packets and admitted receipt digests; no provider effect occurs here",
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
    result = acquire_bounded(ops_repo_root, envs_root, node, ops_revision, envs_revision, target, input_grade="fixture")
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

    unknown = acquire_bounded(ops_repo_root, envs_root, node, ops_revision, envs_revision, None, input_grade="fixture")
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

    again = acquire_bounded(ops_repo_root, envs_root, node, ops_revision, envs_revision, target, input_grade="fixture")
    if canonical(result) != canonical(again):
        raise ClosureError("acquisition-not-deterministic")
    cases.append("same-exact-input-byte-identical")

    if "roccho-dev/adrs" in canonical(result).decode("utf-8") or "contract-drift/authority-source" in canonical(result).decode("utf-8"):
        raise ClosureError("new-adrs-source-became-required-input")
    cases.append("no-new-adrs-cue-adoption-input")

    approved_target_source = fixture_source("approved-target-source", "fixture/approval")
    approved_target_packet = {
        "kind": APPROVED_TARGET_KIND,
        "selected_deploy_revision": SELECTED_DEPLOY_REVISION,
        "envs_revision": envs_revision,
        "source": approved_target_source,
        "target_digest": digest(target),
        "target": target,
    }
    with tempfile.TemporaryDirectory(prefix="governance-approved-target-selftest-") as raw:
        target_path = Path(raw) / "approved-target.json"
        target_path.write_bytes(canonical(approved_target_packet))
        admitted = bytes_digest(target_path.read_bytes())
        selected, provenance = _approved_target_selection(
            target_path, admitted, envs_revision, SELECTED_DEPLOY_REVISION, ops_repo_root, node
        )
        if selected != target or provenance.get("status") != "ADMITTED_INPUT":
            raise ClosureError("approved-target-positive")
        cases.append("approved-target-provenance-positive")

        try:
            _approved_target_selection(
                target_path, "sha256:" + ("f" * 64), envs_revision,
                SELECTED_DEPLOY_REVISION, ops_repo_root, node
            )
        except ClosureError as exc:
            if str(exc) != "approved-target-admission-digest-mismatch":
                raise
        else:
            raise ClosureError("approved-target-unbound-admitted")
        cases.append("approved-target-byte-admission-mismatch-rejected")

        wrong = json.loads(json.dumps(approved_target_packet))
        wrong["target_digest"] = "sha256:" + ("e" * 64)
        target_path.write_bytes(canonical(wrong))
        try:
            _approved_target_selection(
                target_path, bytes_digest(target_path.read_bytes()), envs_revision,
                SELECTED_DEPLOY_REVISION, ops_repo_root, node
            )
        except ClosureError as exc:
            if str(exc) != "approved-target-digest-mismatch":
                raise
        else:
            raise ClosureError("approved-target-semantic-digest-mismatch-admitted")
        cases.append("approved-target-semantic-digest-mismatch-rejected")

        wrong = json.loads(json.dumps(approved_target_packet))
        wrong["selected_deploy_revision"] = "d" * 40
        target_path.write_bytes(canonical(wrong))
        try:
            _approved_target_selection(
                target_path, bytes_digest(target_path.read_bytes()), envs_revision,
                SELECTED_DEPLOY_REVISION, ops_repo_root, node
            )
        except ClosureError as exc:
            if str(exc) != "approved-target-selected-deploy-mismatch":
                raise
        else:
            raise ClosureError("approved-target-wrong-deploy-admitted")
        cases.append("approved-target-selected-deploy-mismatch-rejected")

    evidence_exports = {name: json.loads(json.dumps(normalized[name])) for name in COLLECTIONS}
    provided_contract = evidence_exports["provided"]["rows"][0]["contract"]
    evidence_ref = "fixture.projection.receipt"
    attempt = "attempt-1"
    evidence_exports["observations"] = {
        "source": fixture_source("observations", "fixture/evidence"),
        "rows": [{
            "id": selected_obligation_id(),
            "attempt": attempt,
            "epoch": SELECTED_EPOCH,
            "refs": {"projection": evidence_ref},
        }],
    }
    evidence_receipt = {
        "id": evidence_ref,
        "obligation_id": selected_obligation_id(),
        "role": "projection",
        "attempt": attempt,
        "epoch": SELECTED_EPOCH,
        "source": evidence_exports["provided"]["source"],
        "target": provided_contract["target"],
        "slot": provided_contract["slot"],
        "operation": "cloudflare_workers_secret_put",
        "status": "PASS",
        "readback": "PASS",
        "grade": "real",
    }
    evidence_exports["receipts"] = {
        "source": fixture_source("receipts", "fixture/evidence"),
        "rows": [evidence_receipt],
    }
    evidence_authority = json.loads(json.dumps(normalized["authority"]))
    observed, received, trusted, error = _evidence_inputs(
        evidence_authority,
        evidence_exports["required"]["source"],
        evidence_exports["provided"]["source"],
        evidence_exports["observations"],
        evidence_exports["receipts"],
        {evidence_ref: digest(evidence_receipt)},
    )
    if error is not None:
        raise ClosureError("valid-evidence-input-rejected")
    with_evidence = compose(
        evidence_authority,
        {
            "required": evidence_exports["required"],
            "provided": evidence_exports["provided"],
            "observations": observed,
            "receipts": received,
        },
        ops_repo_root.resolve() / "packages" / "contract-diff",
        ops_revision,
        "fixture",
    )
    if _finding(with_evidence, "EVIDENCE_MISSING"):
        raise ClosureError("valid-evidence-did-not-close-missing")
    cases.append("closed-o-h-input-can-remove-evidence-missing")

    _, _, _, missing_trust = _evidence_inputs(
        json.loads(json.dumps(normalized["authority"])),
        evidence_exports["required"]["source"],
        evidence_exports["provided"]["source"],
        evidence_exports["observations"],
        evidence_exports["receipts"],
        {},
    )
    if missing_trust != "evidence-provenance-unadmitted":
        raise ClosureError("untrusted-evidence-not-unknown")
    cases.append("untrusted-evidence-provenance-is-unknown")

    wrong_receipt = json.loads(json.dumps(evidence_receipt))
    wrong_receipt["attempt"] = "attempt-2"
    drift_exports = json.loads(json.dumps(evidence_exports))
    drift_exports["receipts"]["rows"] = [wrong_receipt]
    drift_authority = json.loads(json.dumps(normalized["authority"]))
    observed, received, _, error = _evidence_inputs(
        drift_authority,
        drift_exports["required"]["source"],
        drift_exports["provided"]["source"],
        drift_exports["observations"],
        drift_exports["receipts"],
        {evidence_ref: digest(wrong_receipt)},
    )
    if error is not None:
        raise ClosureError("drift-evidence-input-rejected-before-comparator")
    drift_result = compose(
        drift_authority,
        {
            "required": drift_exports["required"],
            "provided": drift_exports["provided"],
            "observations": observed,
            "receipts": received,
        },
        ops_repo_root.resolve() / "packages" / "contract-diff",
        ops_revision,
        "fixture",
    )
    if not any(item.get("kind") == "EVIDENCE_DRIFT" and item.get("field") == "attempt"
               for item in drift_result.get("diff", {}).get("findings", [])):
        raise ClosureError("wrong-attempt-not-evidence-drift")
    cases.append("wrong-attempt-is-evidence-drift")

    report = {
        "kind": "governance.contractDriftAcquisition.selftest.v1",
        "status": "pass",
        "authority": False,
        "fixture_target_only": True,
        "raw_acquire_grade": "fixture",
        "production_entry": "nix-pinned-wrapper",
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

    acquire_parser = sub.add_parser("acquire-fixture")
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
        if args.command == "acquire-fixture":
            target = load_json(args.target) if args.target else None
            result = acquire_bounded(
                args.ops_root, args.envs_root, args.node, args.ops_revision, args.envs_revision, target,
                input_grade="fixture",
            )
            args.out.write_bytes(canonical(result) + b"\n")
            sys.stdout.buffer.write(canonical(result) + b"\n")
            return {"CLOSED": 0, "OPEN": 2, "INVALID": 3, "UNKNOWN": 4}.get(result["status"], 3)
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
