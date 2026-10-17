#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

TARGET_ID = "apps"
LOGICAL_REPOSITORY = "roccho-dev/apps"
PROVIDER_REPOSITORY = "roccho-dev/apps"
CLAIM_CEILING = "APPS_ARTIFACT_DECLARATION_AND_EXACT_BUILD_PROJECTION_ONLY"
OBLIGATION_ID = "apps.voice-ui-artifact-auth.v1"
SUBJECT_KEY = "package:apps/voice-ui-artifact-auth"
ROLE = "artifact-build-readback"
EPOCH = "contract-632-apps-finite-v1"
SCOPE_CANDIDATE_FIELD = "appsCandidate"
REQUIREMENT_PATH = "decisions/apps-voice-ui-artifact-auth-requirement-261015.jsonl"
SOURCE_PATHS = {
    "providerClaim": "packages/voice-ui/artifact.jsonl",
    "receiptProducer": "packages/voice-ui/dist.py",
    "buildInput": "flake.lock",
    "comparatorCli": "packages/contract-diff/bin/contract-diff.py",
    "comparatorCore": "packages/contract-diff/core.py",
}
ACCEPTED_FILES = {
    "acceptedDecision": REQUIREMENT_PATH,
    "acceptedRollout": REQUIREMENT_PATH,
}
EXPECTED_NEGATIVE = {
    "contract-drift": "OPEN",
    "missing-observation": "OPEN",
    "wrong-candidate": "OPEN",
    "missing-admission": "UNKNOWN",
}
STATUS_EXIT = {"CLOSED": 0, "OPEN": 2, "INVALID": 3, "UNKNOWN": 4}
COLLECTIONS = ("required", "provided", "observations", "receipts")
EXPECTED_ARTIFACT = {
    "artifact": "voice-ui",
    "kind": "artifact.auth.v1",
    "requiredCapabilities": ["jev-api"],
}
EXPECTED_ARTIFACT_DIGEST = "sha256:0f79ee6819cb68140360b97c27486f2365a7a0ac849ef81702f0ff2536485d82"
EXPECTED_ARTIFACT_BLOB = "44c7f74fb5d6b44d3415079b0e542c6866c86fea"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _digest(value: Any) -> str:
    return _sha_bytes(_canonical(value).encode())


def _need(ok: bool, code: str, detail: Any | None = None) -> None:
    if not ok:
        suffix = "" if detail is None else ":" + _canonical(detail)
        raise ValueError("apps-adapter:" + code + suffix)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_one_jsonl(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    _need(len(rows) == 1 and isinstance(rows[0], dict), "jsonl-single-row", path.as_posix())
    return rows[0]


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical(value) + "\n", encoding="utf-8")


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _source(repository: str, revision: str, path: str, native: Path) -> dict[str, str]:
    _need(native.is_file() and not native.is_symlink(), "source-missing", path)
    return {"repository": repository, "revision": revision, "path": path, "digest": _sha_file(native)}


def _copy_source(repository: str, revision: str, relative: str, native: Path, bundle: Path, bundle_path: str) -> dict[str, Any]:
    destination = bundle / bundle_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(native, destination)
    return {"source": _source(repository, revision, relative, native), "bundlePath": bundle_path}


def _inventory_item(export: dict[str, Any], digest: Callable[[Any], str]) -> dict[str, Any]:
    rows = sorted(export["rows"], key=lambda row: row["id"])
    return {"source": export["source"], "rows_digest": digest(rows), "count": len(rows)}


def _refresh_inventory(packet: dict[str, Any], admission: dict[str, Any], digest: Callable[[Any], str]) -> None:
    admission["inventory"] = {name: _inventory_item(packet[name], digest) for name in COLLECTIONS}


def _compare(cli: Path, packet: Path, admission: Path, cwd: Path) -> tuple[int, dict[str, Any]]:
    process = _run([sys.executable, str(cli), "--input", str(packet), "--admission", str(admission)], cwd)
    _need(process.stdout.strip() != "", "contract-diff-empty", {"exit": process.returncode, "stderr": process.stderr[-2000:]})
    result = json.loads(process.stdout)
    _need(isinstance(result, dict), "contract-diff-object")
    return process.returncode, result


def _contract_from_requirement(row: dict[str, Any], digest: Callable[[Any], str]) -> dict[str, Any]:
    _need(row.get("subject_key") == SUBJECT_KEY, "requirement-subject")
    meaning = row.get("meaning_identity")
    _need(isinstance(meaning, dict), "requirement-meaning")
    subject = meaning.get("subject")
    _need(
        isinstance(subject, dict)
        and subject.get("obligation_id") == OBLIGATION_ID
        and subject.get("repository") == LOGICAL_REPOSITORY
        and subject.get("subject_key") == SUBJECT_KEY,
        "requirement-subject-identity",
    )
    _need(meaning.get("claim_ceiling") == CLAIM_CEILING, "requirement-ceiling")
    contract = meaning.get("contract")
    profile = meaning.get("mandatory_profile")
    _need(isinstance(contract, dict) and isinstance(profile, list), "requirement-contract")
    body = {**contract, "profile": profile}
    return {"obligation_digest": digest(body), **body}


def _contract_from_declaration(artifact: dict[str, Any], executor: dict[str, Any], digest: Callable[[Any], str]) -> dict[str, Any]:
    capabilities = artifact.get("requiredCapabilities") if isinstance(artifact, dict) else None
    _need(
        isinstance(artifact, dict)
        and set(artifact) == {"artifact", "kind", "requiredCapabilities"}
        and artifact.get("artifact") == "voice-ui"
        and artifact.get("kind") == "artifact.auth.v1"
        and isinstance(capabilities, list)
        and len(capabilities) == 1
        and isinstance(capabilities[0], str)
        and capabilities[0] != "",
        "provider-declaration-shape",
    )
    capability = capabilities[0]
    body = {
        "capability": capability,
        "consumer": LOGICAL_REPOSITORY,
        "stage": "build",
        "target": {"account": None, "provider": "nix", "resource": "voice-ui-dist"},
        "slot": "artifact-auth-jsonl",
        "binding": artifact["kind"] + "/" + capability,
        "profile": [{"role": ROLE, "operation": executor["operation"], "readback": executor["readback"], "grade": executor["grade"]}],
    }
    return {"obligation_digest": digest(body), **body}


def _contract_from_source(artifact: dict[str, Any], executor: dict[str, Any], digest: Callable[[Any], str]) -> dict[str, Any]:
    _need(artifact == EXPECTED_ARTIFACT, "provider-declaration")
    return _contract_from_declaration(artifact, executor, digest)


def describe() -> dict[str, Any]:
    return {
        "targetId": TARGET_ID,
        "logicalRepository": LOGICAL_REPOSITORY,
        "providerRepository": PROVIDER_REPOSITORY,
        "claimCeiling": CLAIM_CEILING,
        "obligationId": OBLIGATION_ID,
        "lowerVerifierPath": None,
        "sourcePaths": SOURCE_PATHS,
        "acceptedFiles": ACCEPTED_FILES,
        "expectedNegative": EXPECTED_NEGATIVE,
        "statusExit": STATUS_EXIT,
    }


def required_contract(decision: dict[str, Any], rollout: dict[str, Any], digest: Callable[[Any], str], check_token: Callable[[str], str]) -> tuple[dict[str, Any], dict[str, Any]]:
    del check_token
    _need(decision == rollout, "accepted-source-role-drift")
    return decision, _contract_from_requirement(decision, digest)


def _actual_wrong_source_negative(
    packet: dict[str, Any],
    admission: dict[str, Any],
    cli: Path,
    runtime_root: Path,
    bundle: Path,
    digest: Callable[[Any], str],
    requirement: dict[str, Any],
    executor: dict[str, Any],
) -> dict[str, Any]:
    binding = requirement.get("apps_source_binding")
    _need(isinstance(binding, dict), "source-binding")
    wrong = {"artifact": "voice-ui", "kind": "artifact.auth.v1", "requiredCapabilities": ["wrong-capability"]}
    raw = (_canonical(wrong) + "\n").encode()
    actual_digest, actual_blob = _sha_bytes(raw), _git_blob(raw)
    _need(actual_digest != binding.get("digest") and actual_blob != binding.get("git_blob"), "source-pin-negative")

    artifact_path = bundle / "apps-negative-source-bytes-self-consistent-hash-artifact.jsonl"
    artifact_path.write_bytes(raw)
    _need(_sha_file(artifact_path) == actual_digest and _git_blob(artifact_path.read_bytes()) == actual_blob, "wrong-source-readback")

    bad_packet = copy.deepcopy(packet)
    wrong_source = copy.deepcopy(bad_packet["provided"]["source"])
    wrong_source["digest"] = actual_digest
    wrong_contract = _contract_from_declaration(wrong, executor, digest)
    bad_packet["provided"]["source"] = wrong_source
    bad_packet["provided"]["rows"][0]["contract"] = wrong_contract
    bad_packet["receipts"]["rows"][0]["source"] = wrong_source

    bad_admission = copy.deepcopy(admission)
    receipt = bad_packet["receipts"]["rows"][0]
    bad_admission["evidence"][receipt["id"]] = digest(receipt)
    _refresh_inventory(bad_packet, bad_admission, digest)

    packet_path = bundle / "apps-negative-source-bytes-self-consistent-hash-input.json"
    admission_path = bundle / "apps-negative-source-bytes-self-consistent-hash-admission.json"
    result_path = bundle / "apps-negative-source-bytes-self-consistent-hash-result.json"
    readback_path = bundle / "apps-negative-source-bytes-self-consistent-hash-readback.json"
    _write(packet_path, bad_packet)
    _write(admission_path, bad_admission)
    code, result = _compare(cli, packet_path, admission_path, runtime_root)
    _need(code == STATUS_EXIT["OPEN"] and result.get("status") == "OPEN", "wrong-source-consumer-result", {"exit": code, "result": result})
    _write(result_path, result)

    readback = {
        "kind": "apps.contract632.actualWrongSourceConsumerReadback.v1",
        "status": result["status"],
        "exit": code,
        "rejected": True,
        "actualConsumerExecuted": True,
        "consumer": "contract-diff",
        "inputArtifact": {
            "bundlePath": artifact_path.relative_to(bundle).as_posix(),
            "bytes": len(raw),
            "digest": actual_digest,
            "gitBlob": actual_blob,
        },
        "packetSource": wrong_source,
        "derivedProvidedContract": wrong_contract,
        "acceptedDigest": binding["digest"],
        "acceptedGitBlob": binding["git_blob"],
        "inputDigest": _sha_file(packet_path),
        "admissionDigest": _sha_file(admission_path),
        "resultDigest": _sha_file(result_path),
        "findings": result.get("findings", []),
    }
    _write(readback_path, readback)
    return readback


def _run_extra_negatives(
    packet: dict[str, Any],
    admission: dict[str, Any],
    cli: Path,
    runtime_root: Path,
    bundle: Path,
    digest: Callable[[Any], str],
    standard: dict[str, dict[str, Any]],
    standard_exits: dict[str, int],
    requirement: dict[str, Any],
    executor: dict[str, Any],
) -> dict[str, Any]:
    cases: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}

    missing_requirement = copy.deepcopy(packet)
    missing_requirement["required"]["rows"] = []
    missing_requirement_admission = copy.deepcopy(admission)
    _refresh_inventory(missing_requirement, missing_requirement_admission, digest)
    cases["requirement-row-missing"] = (missing_requirement, missing_requirement_admission)

    missing_provided = copy.deepcopy(packet)
    missing_provided["provided"]["rows"] = []
    missing_provided_admission = copy.deepcopy(admission)
    _refresh_inventory(missing_provided, missing_provided_admission, digest)
    cases["provided-row-missing"] = (missing_provided, missing_provided_admission)

    missing_receipt = copy.deepcopy(packet)
    missing_receipt["receipts"]["rows"] = []
    missing_receipt_admission = copy.deepcopy(admission)
    _refresh_inventory(missing_receipt, missing_receipt_admission, digest)
    cases["required-receipt-missing"] = (missing_receipt, missing_receipt_admission)

    subject_mismatch = copy.deepcopy(packet)
    subject_mismatch["provided"]["rows"][0]["contract"]["consumer"] = "roccho-dev/not-apps"
    subject_mismatch_admission = copy.deepcopy(admission)
    _refresh_inventory(subject_mismatch, subject_mismatch_admission, digest)
    cases["subject-mismatch"] = (subject_mismatch, subject_mismatch_admission)

    invalid_source = copy.deepcopy(packet)
    invalid_source["provided"]["source"]["digest"] = "sha256:invalid"
    invalid_source["receipts"]["rows"][0]["source"] = copy.deepcopy(invalid_source["provided"]["source"])
    invalid_source_admission = copy.deepcopy(admission)
    invalid_receipt = invalid_source["receipts"]["rows"][0]
    invalid_source_admission["evidence"][invalid_receipt["id"]] = digest(invalid_receipt)
    _refresh_inventory(invalid_source, invalid_source_admission, digest)
    cases["source-descriptor-invalid"] = (invalid_source, invalid_source_admission)

    results: dict[str, Any] = {}
    for name, (bad_packet, bad_admission) in cases.items():
        packet_path = bundle / f"apps-negative-{name}-input.json"
        admission_path = bundle / f"apps-negative-{name}-admission.json"
        result_path = bundle / f"apps-negative-{name}-result.json"
        _write(packet_path, bad_packet)
        _write(admission_path, bad_admission)
        code, result = _compare(cli, packet_path, admission_path, runtime_root)
        _need(code in {2, 3, 4} and result.get("status") != "CLOSED", "extra-negative", {"case": name, "exit": code, "result": result})
        _write(result_path, result)
        results[name] = {
            "status": result["status"],
            "exit": code,
            "rejected": True,
            "actualConsumerExecuted": True,
            "inputDigest": _sha_file(packet_path),
            "admissionDigest": _sha_file(admission_path),
            "resultDigest": _sha_file(result_path),
        }

    aliases = {
        "contract-mismatch": "contract-drift",
        "observation-row-missing": "missing-observation",
        "stale-candidate": "wrong-candidate",
        "missing-admission": "missing-admission",
    }
    for name, source in aliases.items():
        result_path = bundle / f"contract-diff-negative-{source}.json"
        results[name] = {
            "status": standard[source]["status"],
            "exit": standard_exits[source],
            "rejected": standard_exits[source] != 0,
            "actualConsumerExecuted": True,
            "resultDigest": _sha_file(result_path),
        }

    results["source-bytes-self-consistent-hash"] = _actual_wrong_source_negative(
        packet,
        admission,
        cli,
        runtime_root,
        bundle,
        digest,
        requirement,
        executor,
    )

    expected = {
        "requirement-row-missing",
        "provided-row-missing",
        "required-receipt-missing",
        "subject-mismatch",
        "source-descriptor-invalid",
        "contract-mismatch",
        "observation-row-missing",
        "stale-candidate",
        "missing-admission",
        "source-bytes-self-consistent-hash",
    }
    _need(set(results) == expected and all(row["rejected"] for row in results.values()), "negative-coverage")
    _need(all(row.get("actualConsumerExecuted") is True for row in results.values()), "negative-consumer-execution")
    exit_universe = sorted({0, *[row["exit"] for row in results.values()]})
    _need(exit_universe == [0, 2, 3, 4], "exit-universe", exit_universe)
    report = {
        "kind": "apps.contract632.targetNegatives.v2",
        "status": "pass",
        "authority": False,
        "subjectKey": SUBJECT_KEY,
        "obligationId": OBLIGATION_ID,
        "consumer": "contract-diff",
        "allCasesExecutedByConsumer": True,
        "cases": results,
        "exitUniverse": exit_universe,
    }
    _write(bundle / "apps-target-negatives.json", report)
    return report


def expected_evidence(
    *,
    scope: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    bindings: dict[str, Any],
    bundle: Path,
    receipt_rows: list[dict[str, Any]],
    read_object: Callable[[Path, str], dict[str, Any]],
    sha256_file: Callable[[Path], str],
    digest: Callable[[Any], str],
    required_contract: dict[str, Any],
) -> dict[str, Any]:
    receipt = read_object(bundle / "apps-artifact-build-receipt.json", "apps-build-receipt")
    negatives = read_object(bundle / "apps-target-negatives.json", "apps-target-negatives")
    _need(receipt.get("operation") == "nix-build-voice-ui-dist", "receipt-operation")
    _need(receipt.get("grade") == "source", "receipt-grade")
    _need(receipt.get("readback") == "PASS" and receipt.get("status") == "PASS", "receipt-result")
    _need(receipt.get("sourceDigest") == receipt.get("outputDigest") == EXPECTED_ARTIFACT_DIGEST, "receipt-projection")
    _need(negatives.get("status") == "pass" and negatives.get("exitUniverse") == [0, 2, 3, 4], "negative-report")
    _need(negatives.get("allCasesExecutedByConsumer") is True, "negative-consumer-boundary")
    _need(all(row.get("rejected") is True and row.get("actualConsumerExecuted") is True for row in negatives.get("cases", {}).values()), "negative-report-cases")
    return {
        "kind": "apps.contract632.phase4Evidence.v2",
        "status": "PASS",
        "authority": False,
        "adoption": False,
        "releasePublished": False,
        "claimCeiling": CLAIM_CEILING,
        "scope": scope,
        "acceptedRequirement": {
            "source": sources["acceptedRollout"],
            "decisionSource": sources["acceptedDecision"],
            "obligationId": OBLIGATION_ID,
            "subjectKey": SUBJECT_KEY,
            "contract": required_contract,
        },
        "provider": {"source": sources["providerClaim"], "claimDigest": sha256_file(bundle / bindings["providerClaim"]["bundlePath"])},
        "observation": {"source": sources["observer"], "candidate": scope[SCOPE_CANDIDATE_FIELD]},
        "receipt": {
            "source": sources["receiptProducer"],
            "buildInputSource": sources["buildInput"],
            "actualReceiptDigest": sha256_file(bundle / "apps-artifact-build-receipt.json"),
            "normalizedReceiptDigest": digest(receipt_rows[0]),
            "role": ROLE,
            "operation": "nix-build-voice-ui-dist",
            "grade": "source",
            "readback": True,
            "outputPath": ".envs/artifact.jsonl",
        },
        "comparator": {
            "source": sources["comparatorCore"],
            "positive": read_object(bundle / "contract-diff-positive.json", "positive"),
            "negative": {name: read_object(bundle / f"contract-diff-negative-{name}.json", "negative:" + name) for name in EXPECTED_NEGATIVE},
        },
        "targetNegatives": negatives,
        "remaining": 0,
    }


def produce(context: dict[str, Any]) -> dict[str, Any]:
    bundle = Path(context["bundle"]).resolve()
    target_source = Path(context["targetSourceRoot"]).resolve()
    accepted_source = Path(context["acceptedRequirementRoot"]).resolve()
    runtime_source = Path(context["contractRuntimeRoot"]).resolve()
    evidence_root = Path(context["evidenceInputRoot"]).resolve()
    observer_root = Path(context["observerRoot"]).resolve()
    target_candidate = str(context["targetCandidate"])
    accepted_revision = str(context["acceptedRequirementRevision"])
    governance_candidate = str(context["governanceCandidate"])
    adapter_path = str(context["adapterPath"])
    executor = context["evidenceExecutor"]

    _need(not bundle.exists(), "bundle-exists")
    bundle.mkdir(parents=True)

    requirement_path = accepted_source / REQUIREMENT_PATH
    requirement = _read_one_jsonl(requirement_path)
    required = _contract_from_requirement(requirement, _digest)

    artifact_path = target_source / SOURCE_PATHS["providerClaim"]
    artifact_raw = artifact_path.read_bytes()
    _need(_sha_bytes(artifact_raw) == EXPECTED_ARTIFACT_DIGEST and _git_blob(artifact_raw) == EXPECTED_ARTIFACT_BLOB, "provider-source-pin")
    artifact = _read_one_jsonl(artifact_path)
    provided = _contract_from_source(artifact, executor, _digest)
    _need(required == provided, "required-provided-drift")

    evidence = _read(evidence_root / "evidence.json")
    _need(evidence.get("mode") == "exact-existing-release", "evidence-mode")
    _need(evidence.get("targetId") == TARGET_ID and evidence.get("candidate") == target_candidate, "evidence-identity")
    _need(evidence.get("executor") == executor, "evidence-executor")
    receipt = evidence.get("receipt")
    _need(isinstance(receipt, dict), "evidence-receipt")
    _need(receipt.get("targetId") == TARGET_ID and receipt.get("candidate") == target_candidate, "evidence-receipt-identity")
    _need(receipt.get("operation") == executor["operation"] and receipt.get("grade") == executor["grade"], "evidence-receipt-profile")
    _need(receipt.get("status") == "PASS" and receipt.get("readback") == "PASS", "evidence-receipt-result")
    _need((evidence_root / "source-artifact.jsonl").read_bytes() == artifact_raw, "evidence-source")
    _need((evidence_root / "output-artifact.jsonl").read_bytes() == artifact_raw, "evidence-output")
    _need(receipt.get("sourceDigest") == receipt.get("outputDigest") == EXPECTED_ARTIFACT_DIGEST, "evidence-projection-digest")
    manifest = _read(evidence_root / "dist-manifest.json")
    _need(manifest.get("auth") == ".envs/artifact.jsonl", "evidence-output-path")
    full_asset = evidence_root.parent / f"{evidence_root.name}-full" / "voice-ui-dist.zip"
    _need(full_asset.is_file() and full_asset.stat().st_size == 62585992, "full-asset-consumed")

    bindings: dict[str, Any] = {
        "providerClaim": _copy_source(PROVIDER_REPOSITORY, target_candidate, SOURCE_PATHS["providerClaim"], artifact_path, bundle, "sources/apps/artifact.jsonl"),
        "receiptProducer": _copy_source(PROVIDER_REPOSITORY, target_candidate, SOURCE_PATHS["receiptProducer"], target_source / SOURCE_PATHS["receiptProducer"], bundle, "sources/apps/dist.py"),
        "buildInput": _copy_source(PROVIDER_REPOSITORY, target_candidate, SOURCE_PATHS["buildInput"], target_source / SOURCE_PATHS["buildInput"], bundle, "sources/apps/flake.lock"),
        "comparatorCli": _copy_source("roccho-org/ops", "5eb98c82417b399978c1e38aebab5e3fb39752d4", SOURCE_PATHS["comparatorCli"], runtime_source / SOURCE_PATHS["comparatorCli"], bundle, "sources/runtime/contract-diff.py"),
        "comparatorCore": _copy_source("roccho-org/ops", "5eb98c82417b399978c1e38aebab5e3fb39752d4", SOURCE_PATHS["comparatorCore"], runtime_source / SOURCE_PATHS["comparatorCore"], bundle, "sources/runtime/contract-diff-core.py"),
        "acceptedDecision": _copy_source("roccho-dev/adrs", accepted_revision, REQUIREMENT_PATH, requirement_path, bundle, "sources/adrs/apps-requirement-decision.jsonl"),
        "acceptedRollout": _copy_source("roccho-dev/adrs", accepted_revision, REQUIREMENT_PATH, requirement_path, bundle, "sources/adrs/apps-requirement-rollout.jsonl"),
        "observer": _copy_source("roccho-dev/governance", governance_candidate, adapter_path, observer_root / adapter_path, bundle, "sources/observer/source"),
    }
    _write(bundle / "source-bindings.json", bindings)
    _write(bundle / "apps-artifact-build-receipt.json", receipt)

    receipt_id = f"receipt:{target_candidate}:{ROLE}"
    receipt_row = {
        "id": receipt_id,
        "obligation_id": OBLIGATION_ID,
        "role": ROLE,
        "attempt": target_candidate,
        "epoch": EPOCH,
        "source": bindings["providerClaim"]["source"],
        "target": provided["target"],
        "slot": provided["slot"],
        "operation": executor["operation"],
        "status": "PASS",
        "readback": "PASS",
        "grade": executor["grade"],
    }
    packet = {
        "kind": "contractDiffInput.v1",
        "required": {"source": bindings["acceptedRollout"]["source"], "rows": [{"id": OBLIGATION_ID, "contract": required}]},
        "provided": {"source": bindings["providerClaim"]["source"], "rows": [{"id": OBLIGATION_ID, "contract": provided, "evidence_refs": {ROLE: receipt_id}}]},
        "observations": {"source": bindings["observer"]["source"], "rows": [{"id": OBLIGATION_ID, "attempt": target_candidate, "epoch": EPOCH, "refs": {ROLE: receipt_id}}]},
        "receipts": {"source": bindings["receiptProducer"]["source"], "rows": [receipt_row]},
    }
    admission = {
        "kind": "contractDiffAdmission.v1",
        "scope": {"id": "contract-632-phase4-apps-finite", "authority": bindings["acceptedDecision"]["source"], "epoch": EPOCH, "allow_empty": False, "grade": "source", "excluded_ids": []},
        "universe": [{"id": OBLIGATION_ID, "obligation_digest": required["obligation_digest"], "profile": required["profile"]}],
        "inventory": {},
        "evidence": {receipt_id: _digest(receipt_row)},
    }
    _refresh_inventory(packet, admission, _digest)
    _write(bundle / "contract-diff-input.json", packet)
    _write(bundle / "contract-diff-admission.json", admission)

    cli = runtime_source / SOURCE_PATHS["comparatorCli"]
    positive_code, positive = _compare(cli, bundle / "contract-diff-input.json", bundle / "contract-diff-admission.json", runtime_source)
    _need(positive_code == 0 and positive.get("status") == "CLOSED" and positive.get("findings") == [], "positive", {"exit": positive_code, "result": positive})
    _write(bundle / "contract-diff-positive.json", positive)

    cases: dict[str, tuple[dict[str, Any], dict[str, Any], str]] = {}
    drift_packet = copy.deepcopy(packet)
    drift_packet["provided"]["rows"][0]["contract"]["target"]["resource"] = "wrong-voice-ui-dist"
    drift_admission = copy.deepcopy(admission)
    _refresh_inventory(drift_packet, drift_admission, _digest)
    cases["contract-drift"] = (drift_packet, drift_admission, "OPEN")

    missing_observation = copy.deepcopy(packet)
    missing_observation["observations"]["rows"] = []
    missing_observation_admission = copy.deepcopy(admission)
    _refresh_inventory(missing_observation, missing_observation_admission, _digest)
    cases["missing-observation"] = (missing_observation, missing_observation_admission, "OPEN")

    stale = copy.deepcopy(packet)
    stale["observations"]["rows"][0]["attempt"] = "0" * 40
    stale_admission = copy.deepcopy(admission)
    _refresh_inventory(stale, stale_admission, _digest)
    cases["wrong-candidate"] = (stale, stale_admission, "OPEN")
    cases["missing-admission"] = (packet, {}, "UNKNOWN")

    standard_results: dict[str, dict[str, Any]] = {}
    standard_exits: dict[str, int] = {}
    for name, (bad_packet, bad_admission, expected) in cases.items():
        packet_path = bundle / f"negative-{name}-input.json"
        admission_path = bundle / f"negative-{name}-admission.json"
        result_path = bundle / f"contract-diff-negative-{name}.json"
        _write(packet_path, bad_packet)
        _write(admission_path, bad_admission)
        code, result = _compare(cli, packet_path, admission_path, runtime_source)
        _need(result.get("status") == expected and code == STATUS_EXIT[expected], "standard-negative", {"case": name, "exit": code, "result": result})
        _write(result_path, result)
        standard_results[name], standard_exits[name] = result, code

    _run_extra_negatives(packet, admission, cli, runtime_source, bundle, _digest, standard_results, standard_exits, requirement, executor)

    scope = {
        "kind": "apps.contract632.phase4RunScope.v1",
        "authority": False,
        "scopeId": "contract-632-phase4-apps-finite",
        "selectedObligations": [OBLIGATION_ID],
        SCOPE_CANDIDATE_FIELD: target_candidate,
        "subjectKey": SUBJECT_KEY,
        "governanceRevision": accepted_revision,
        "acceptedRequirementDigest": required["obligation_digest"],
        "requiredEvidenceTypes": [ROLE],
    }
    _write(bundle / "run-scope.json", scope)
    evidence_value = expected_evidence(
        scope=scope,
        sources={key: value["source"] for key, value in bindings.items()},
        bindings=bindings,
        bundle=bundle,
        receipt_rows=[receipt_row],
        read_object=lambda path, label: _read(path),
        sha256_file=_sha_file,
        digest=_digest,
        required_contract=required,
    )
    _write(bundle / "phase4-evidence.json", evidence_value)
    manifest_rows = [
        {"path": path.relative_to(bundle).as_posix(), "sha256": _sha_file(path)}
        for path in sorted(bundle.rglob("*"))
        if path.is_file() and path.name != "bundle-manifest.json"
    ]
    _write(bundle / "bundle-manifest.json", manifest_rows)
    return {
        "kind": "governance.packageContractTargetMaterials.v1",
        "targetId": TARGET_ID,
        "bundle": str(bundle),
        "producerFiles": ["apps-artifact-build-receipt.json", "apps-target-negatives.json"],
        "authority": False,
    }
