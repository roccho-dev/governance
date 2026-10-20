#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable

TARGET_ID = "logger"
LOGICAL_REPOSITORY = "roccho-org/ops+roccho-dev/apps"
PROVIDER_REPOSITORY = "roccho-org/ops"
CLAIM_CEILING = "LOGGER_SELECTED_SCOPE_ESTABLISHED_NOT_OPERATIONAL_ADOPTION"
OBLIGATION_ID = "ops.logger-language-neutral-design.v1"
SUBJECT_KEY = "design:logger-language-neutral"
ROLE = "logger-establishment"
EPOCH = "logger-language-neutral-establishment-v1"
SCOPE_CANDIDATE_FIELD = "retainedKCandidate"
REQUIREMENT_PATH = "decisions/logger-language-neutral-contract-admission-261020.jsonl"
RAW_ID = "raw.adrs.logger_language_neutral_contract_admission.261020.02"
MEANING = "sha256:ab3c271e57ba33a7e663f99d417680f6044cc59c099e5223978e2e4ef6811e3c"
K_ROOT = "packages/shiftleft-admission/tests/fixtures/logger-language-neutral-establishment"
SOURCE_PATHS = {
    "retainedManifest": f"{K_ROOT}/manifest.json",
    "retainedArtifact": f"{K_ROOT}/technical-closure.zip",
    "independentJudgment": f"{K_ROOT}/r-v32-capture.json",
    "comparatorCli": "packages/contract-diff/bin/contract-diff.py",
    "comparatorCore": "packages/contract-diff/core.py",
}
ACCEPTED_FILES = {"acceptedDecision": REQUIREMENT_PATH, "acceptedRollout": REQUIREMENT_PATH}
EXPECTED_NEGATIVE = {
    "contract-drift": "OPEN",
    "missing-observation": "OPEN",
    "wrong-candidate": "OPEN",
    "missing-admission": "UNKNOWN",
}
STATUS_EXIT = {"CLOSED": 0, "OPEN": 2, "INVALID": 3, "UNKNOWN": 4}
REQUIRED_SOURCE_ROLE = "acceptedRollout"
PROVIDED_SOURCE_ROLE = "retainedArtifact"
RECEIPT_SOURCE_ROLE = "independentJudgment"
EXPECTED_REQUIRED = [
    "purpose_scope_coverage",
    "shared_meaning",
    "cross_language_interoperability",
    "pure_application_boundary",
    "environment_transport",
    "host_context_ownership",
    "supply_consumption_binding",
    "actual_data_use",
    "traceable_evidence",
    "bounded_safe_failure",
    "compatibility",
    "causal_design_closure",
    "small_extensible_design",
]
EXPECTED_PROFILES = {
    "cli_batch": "implemented_observed",
    "library": "implemented_observed",
    "browser": "implemented_observed",
    "service": "supported_design_only",
    "worker": "supported_design_only",
}
EXPECTED_OBSERVATION = {
    "repository": "roccho-org/ops",
    "revision": "3372357c67803d0b8c0875eea70bcc642391fa5a",
    "tree": "19f38cc4ea3eef3cb7a99bfb1823455aa53dce11",
}
EXPECTED_PROVIDER = {
    "repository": "roccho-org/ops",
    "role": "provider",
    "revision": "fe968fc6b8919fed48151a57f421667bce0aac87",
    "tree": "b306bf999aba32a678ac48b5a56e4b4a0a3c0cf8",
}
EXPECTED_CONSUMER = {
    "repository": "roccho-dev/apps",
    "role": "consumer",
    "revision": "17c0108a5c2549ffaf7cef791a569f2e1926659f",
    "tree": "3d603665d54c83dd770873870c66863959904b42",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


def _sha_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _need(ok: bool, code: str, detail: Any | None = None) -> None:
    if not ok:
        suffix = "" if detail is None else ":" + _canonical(detail)
        raise ValueError("logger-adapter:" + code + suffix)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_one(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    _need(len(rows) == 1 and isinstance(rows[0], dict), "single-row", path.as_posix())
    return rows[0]


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical(value) + "\n", encoding="utf-8")


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _source(repository: str, revision: str, relative: str, native: Path) -> dict[str, str]:
    _need(native.is_file() and not native.is_symlink(), "source-missing", relative)
    return {"repository": repository, "revision": revision, "path": relative, "digest": _sha_file(native)}


def _copy_source(repository: str, revision: str, relative: str, native: Path, bundle: Path, bundle_path: str) -> dict[str, Any]:
    destination = bundle / bundle_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(native, destination)
    return {"source": _source(repository, revision, relative, native), "bundlePath": bundle_path}


def _semantic(row: dict[str, Any]) -> dict[str, Any]:
    _need(row.get("schema") == "adr_raw_event.v1", "admission-schema")
    _need(row.get("raw_id") == RAW_ID and row.get("subject_key") == SUBJECT_KEY, "admission-identity")
    authority = row.get("authority")
    _need(isinstance(authority, dict) and authority.get("meaning_admitted") is True and authority.get("current_selected") is True, "admission-authority")
    meaning = row.get("meaning_identity")
    identity = row.get("meaning_identity_contract")
    scope = row.get("admission_scope")
    _need(isinstance(meaning, dict) and isinstance(identity, dict) and isinstance(scope, dict), "admission-shape")
    subject = meaning.get("subject")
    required = meaning.get("required")
    _need(isinstance(subject, dict) and subject.get("obligation_id") == OBLIGATION_ID, "obligation")
    _need(identity.get("meaning_digest") == MEANING, "meaning")
    _need(isinstance(required, dict) and list(required) == EXPECTED_REQUIRED, "required-universe")
    _need(scope.get("applicable_required") == EXPECTED_REQUIRED, "applicable-required")
    _need(scope.get("profile_targets") == EXPECTED_PROFILES, "profile-targets")
    _need(scope.get("technical_observation") == EXPECTED_OBSERVATION, "observation")
    repaired = scope.get("repaired_tree_set")
    _need(repaired == [EXPECTED_PROVIDER, EXPECTED_CONSUMER], "repaired-tree-set")
    return {
        "meaningSha256": MEANING,
        "obligationId": OBLIGATION_ID,
        "required": required,
        "profileTargets": EXPECTED_PROFILES,
        "targetRepositories": subject.get("target_repositories"),
        "technicalObservation": EXPECTED_OBSERVATION,
        "repairedTreeSet": repaired,
    }


def _contract(row: dict[str, Any], digest: Callable[[Any], str]) -> dict[str, Any]:
    semantic = _semantic(row)
    body = {
        "capability": "logger-language-neutral-design",
        "consumer": LOGICAL_REPOSITORY,
        "stage": "contract-establishment",
        "target": {"provider": "github", "resource": "logger-language-neutral-design", "account": "selected-scope"},
        "slot": OBLIGATION_ID,
        "binding": MEANING,
        "profile": [{"role": ROLE, "operation": "logger-language-neutral-establishment", "readback": True, "grade": "real"}],
    }
    return {"obligation_digest": digest(semantic), **body}


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
    return decision, _contract(decision, digest)


def _verify_k(target_source: Path) -> dict[str, Any]:
    manifest_path = target_source / SOURCE_PATHS["retainedManifest"]
    artifact_path = target_source / SOURCE_PATHS["retainedArtifact"]
    judgment_path = target_source / SOURCE_PATHS["independentJudgment"]
    manifest = _read(manifest_path)
    judgment = _read(judgment_path)
    _need(manifest.get("schema") == "ops.logger-language-neutral.retained-k/1" and manifest.get("authority") is False, "k-manifest")
    _need(manifest.get("canonicalMeaning") == {
        "repository": "roccho-dev/adrs",
        "revision": "6e4abcd22dbee397105625b6041ce1a0d4720182",
        "tree": "cf28509d770022d2be6e4d172b0ce8b9486cced1",
        "path": REQUIREMENT_PATH,
        "gitBlob": "9371fed680451f58976a00fda0a71e4fbb54f68f",
        "rawId": RAW_ID,
        "meaningSha256": MEANING,
    }, "k-canonical")
    _need(manifest.get("selectedTechnicalSet") == {
        "observation": EXPECTED_OBSERVATION,
        "provider": {k: v for k, v in EXPECTED_PROVIDER.items() if k != "role"},
        "consumer": {k: v for k, v in EXPECTED_CONSUMER.items() if k != "role"},
    }, "k-selected-set")
    technical = manifest.get("technicalArtifact")
    _need(isinstance(technical, dict), "k-artifact-spec")
    _need(artifact_path.stat().st_size == technical.get("bytes") == 98368, "k-artifact-size")
    _need(_sha_file(artifact_path) == technical.get("sha256") == "sha256:5ac5df9deb5bf6c9a36de31e6d534b23673f0d5016ae7d576b2cd716741000a7", "k-artifact-digest")
    required_entries = technical.get("requiredEntries")
    _need(isinstance(required_entries, dict), "k-entry-spec")
    with zipfile.ZipFile(artifact_path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        _need(len(names) == len(set(names)) == 37, "k-entry-universe")
        bodies = {name: archive.read(name) for name in names}
    for name, expected in required_entries.items():
        _need(name in bodies and "sha256:" + hashlib.sha256(bodies[name]).hexdigest() == expected, "k-entry", name)
    sums = {}
    for line in bodies["SHA256SUMS"].decode("utf-8").splitlines():
        digest_value, name = line.split("  ", 1)
        _need(name not in sums, "k-sum-duplicate", name)
        sums[name] = digest_value
    _need(set(sums) == set(bodies) - {"SHA256SUMS"}, "k-sum-universe")
    for name, digest_value in sums.items():
        _need(hashlib.sha256(bodies[name]).hexdigest() == digest_value, "k-sum", name)
    finding = json.loads(bodies["finding.json"])
    closure = json.loads(bodies["closure.json"])
    metadata = json.loads(bodies["metadata.json"])
    browser = json.loads(bodies["browser.json"])
    interchange = json.loads(bodies["interoperability.json"])
    _need(finding.get("candidate", {}).get("meaningSha256") == MEANING, "k-finding-meaning")
    _need(finding.get("coverage") == {"applicable": 13, "evaluated": 13, "met": 8, "unmet": 5, "unknown": 0, "conflict": 0, "stale": 0}, "k-finding-coverage")
    profiles = finding.get("supportMatrix", {}).get("runtimeProfiles", {})
    _need({name: profiles.get(name, {}).get("targetState") for name in EXPECTED_PROFILES} == EXPECTED_PROFILES, "k-profile-matrix")
    _need(closure.get("contract", {}).get("meaningSha256") == MEANING and closure.get("contract", {}).get("obligationId") == OBLIGATION_ID, "k-closure-contract")
    _need(closure.get("status") == "CONFORMANT" and closure.get("coverage") == {"applicable": 13, "evaluated": 13, "met": 13, "unmet": 0, "unknown": 0, "conflict": 0, "stale": 0, "residual": 0}, "k-closure-status")
    _need(list(closure.get("obligations", {})) == EXPECTED_REQUIRED, "k-closure-obligations")
    _need(closure.get("repaired", {}).get("observation") == {"revision": EXPECTED_OBSERVATION["revision"], "tree": EXPECTED_OBSERVATION["tree"]}, "k-closure-observation")
    provider = closure.get("repaired", {}).get("provider", {})
    consumer = closure.get("repaired", {}).get("consumer", {})
    _need({k: provider.get(k) for k in ("repository", "revision", "tree")} == {k: EXPECTED_PROVIDER[k] for k in ("repository", "revision", "tree")}, "k-provider")
    _need({k: consumer.get(k) for k in ("repository", "revision", "tree")} == {k: EXPECTED_CONSUMER[k] for k in ("repository", "revision", "tree")}, "k-consumer")
    _need(set(closure.get("decisions", {})) == {"cross_language_interoperability", "environment_transport", "supply_consumption_binding", "bounded_safe_failure", "causal_design_closure"}, "k-causality")
    _need(metadata.get("observationHead") == EXPECTED_OBSERVATION["revision"] and metadata.get("observationTree") == EXPECTED_OBSERVATION["tree"] and metadata.get("technicalConformance") is True, "k-metadata")
    _need(browser.get("status") == "PASS" and browser.get("providerRevision") == EXPECTED_PROVIDER["revision"] and browser.get("action") == "inspect-judgment-provider", "k-browser")
    _need(interchange.get("status") == "PASS" and interchange.get("implementation", {}).get("pythonDelegatesToNode") is False and interchange.get("interchange") == {"javascriptToPython": "byte-identical", "pythonToJavascript": "byte-identical", "rows": 16}, "k-interchange")
    _need(judgment.get("schema") == "ops.logger-language-neutral.independent-technical-judgment-capture/1" and judgment.get("authority") is False, "k-judgment")
    _need(judgment.get("source", {}).get("commentId") == 6283358664 and judgment.get("source", {}).get("reviewRole") == "R", "k-judgment-source")
    _need(judgment.get("target", {}).get("meaningSha256") == MEANING, "k-judgment-meaning")
    _need(judgment.get("verdict", {}).get("repaired") == {"applicable": 13, "evaluated": 13, "met": 13, "unmet": 0, "unknown": 0, "conflict": 0, "stale": 0, "residual": 0, "status": "CONFORMANT"}, "k-judgment-verdict")
    return {
        "kind": "governance.loggerRetainedKReadback.v1",
        "status": "PASS",
        "authority": False,
        "artifactDigest": _sha_file(artifact_path),
        "manifestDigest": _sha_file(manifest_path),
        "judgmentDigest": _sha_file(judgment_path),
        "entriesVerified": len(bodies),
        "bodySumsVerified": len(sums),
        "oldCoverage": closure["old"]["coverage"],
        "currentCoverage": closure["coverage"],
        "profiles": EXPECTED_PROFILES,
        "meaningSha256": MEANING,
    }


def _compare(cli: Path, packet: Path, admission: Path, cwd: Path) -> tuple[int, dict[str, Any]]:
    process = _run([sys.executable, str(cli), "--input", str(packet), "--admission", str(admission)], cwd)
    _need(process.stdout.strip() != "", "contract-diff-empty", {"exit": process.returncode, "stderr": process.stderr[-2000:]})
    result = json.loads(process.stdout)
    return process.returncode, result


def expected_evidence(*, scope: dict[str, Any], sources: dict[str, dict[str, Any]], bindings: dict[str, Any], bundle: Path, receipt_rows: list[dict[str, Any]], read_object: Callable[[Path, str], dict[str, Any]], sha256_file: Callable[[Path], str], digest: Callable[[Any], str], required_contract: dict[str, Any]) -> dict[str, Any]:
    k = read_object(bundle / "logger-k-readback.json", "logger-k")
    cold = read_object(bundle / "logger-cold-selection.json", "logger-cold")
    _need(k.get("status") == "PASS" and k.get("currentCoverage", {}).get("met") == 13, "evidence-k")
    _need(cold.get("status") == "PASS" and cold.get("rawId") == RAW_ID and cold.get("meaningSha256") == MEANING, "evidence-cold")
    return {
        "kind": "governance.loggerLanguageNeutralEstablishmentEvidence.v1",
        "status": "PASS",
        "authority": False,
        "adoption": False,
        "releasePublished": False,
        "claimCeiling": CLAIM_CEILING,
        "scope": scope,
        "acceptedRequirement": {"source": sources["acceptedRollout"], "decisionSource": sources["acceptedDecision"], "obligationId": OBLIGATION_ID, "contract": required_contract},
        "provided": {"source": sources["retainedArtifact"], "manifestSource": sources["retainedManifest"], "contract": required_contract},
        "observation": {"source": sources["observer"], "candidate": scope[SCOPE_CANDIDATE_FIELD]},
        "receipt": {"source": sources["independentJudgment"], "normalizedReceiptDigest": digest(receipt_rows[0]), "role": ROLE, "operation": "logger-language-neutral-establishment", "grade": "real", "readback": True},
        "retainedK": k,
        "coldSelection": cold,
        "comparator": {"source": sources["comparatorCore"], "positive": read_object(bundle / "contract-diff-positive.json", "positive"), "negative": {name: read_object(bundle / f"contract-diff-negative-{name}.json", "negative:" + name) for name in EXPECTED_NEGATIVE}},
        "remaining": 0,
    }


def produce(context: dict[str, Any]) -> dict[str, Any]:
    bundle = Path(context["bundle"]).resolve()
    target_source = Path(context["targetSourceRoot"]).resolve()
    accepted_source = Path(context["acceptedRequirementRoot"]).resolve()
    runtime_source = Path(context["contractRuntimeRoot"]).resolve()
    observer_root = Path(context["observerRoot"]).resolve()
    target_candidate = str(context["targetCandidate"])
    accepted_revision = str(context["acceptedRequirementRevision"])
    governance_candidate = str(context["governanceCandidate"])
    adapter_path = str(context["adapterPath"])
    executor = context["evidenceExecutor"]
    _need(not bundle.exists(), "bundle-exists")
    bundle.mkdir(parents=True)

    requirement_path = accepted_source / REQUIREMENT_PATH
    requirement = _read_one(requirement_path)
    required = _contract(requirement, _digest)
    k = _verify_k(target_source)
    _write(bundle / "logger-k-readback.json", k)

    from tools.package_contract_port_cold import select_cold_record
    selected = select_cold_record(root=accepted_source, code_root=accepted_source, git="git", reference="HEAD", revision=accepted_revision, path=REQUIREMENT_PATH, record_id=RAW_ID)
    _need(selected["object"] == requirement, "cold-selected-object")
    cold = {
        "kind": "governance.loggerColdSelection.v1",
        "status": "PASS",
        "authority": False,
        "rawId": RAW_ID,
        "source": selected["source"],
        "codecBlob": selected["codecBlob"],
        "objectDigest": _digest(selected["object"]),
        "meaningSha256": MEANING,
    }
    _write(bundle / "logger-cold-selection.json", cold)

    bindings: dict[str, Any] = {
        "retainedManifest": _copy_source(PROVIDER_REPOSITORY, target_candidate, SOURCE_PATHS["retainedManifest"], target_source / SOURCE_PATHS["retainedManifest"], bundle, "sources/ops/retained-k-manifest.json"),
        "retainedArtifact": _copy_source(PROVIDER_REPOSITORY, target_candidate, SOURCE_PATHS["retainedArtifact"], target_source / SOURCE_PATHS["retainedArtifact"], bundle, "sources/ops/technical-closure.zip"),
        "independentJudgment": _copy_source(PROVIDER_REPOSITORY, target_candidate, SOURCE_PATHS["independentJudgment"], target_source / SOURCE_PATHS["independentJudgment"], bundle, "sources/ops/r-v32-capture.json"),
        "comparatorCli": _copy_source("roccho-org/ops", "5eb98c82417b399978c1e38aebab5e3fb39752d4", SOURCE_PATHS["comparatorCli"], runtime_source / SOURCE_PATHS["comparatorCli"], bundle, "sources/runtime/contract-diff.py"),
        "comparatorCore": _copy_source("roccho-org/ops", "5eb98c82417b399978c1e38aebab5e3fb39752d4", SOURCE_PATHS["comparatorCore"], runtime_source / SOURCE_PATHS["comparatorCore"], bundle, "sources/runtime/contract-diff-core.py"),
        "acceptedDecision": _copy_source("roccho-dev/adrs", accepted_revision, REQUIREMENT_PATH, requirement_path, bundle, "sources/adrs/logger-admission-decision.jsonl"),
        "acceptedRollout": _copy_source("roccho-dev/adrs", accepted_revision, REQUIREMENT_PATH, requirement_path, bundle, "sources/adrs/logger-admission-rollout.jsonl"),
        "observer": _copy_source("roccho-dev/governance", governance_candidate, adapter_path, observer_root / adapter_path, bundle, "sources/observer/source"),
    }
    _write(bundle / "source-bindings.json", bindings)

    receipt_id = f"receipt:{target_candidate}:{ROLE}"
    receipt = {
        "id": receipt_id,
        "obligation_id": OBLIGATION_ID,
        "role": ROLE,
        "attempt": target_candidate,
        "epoch": EPOCH,
        "source": bindings["retainedArtifact"]["source"],
        "target": required["target"],
        "slot": required["slot"],
        "operation": executor["operation"],
        "status": "PASS",
        "readback": "PASS",
        "grade": executor["grade"],
    }
    packet = {
        "kind": "contractDiffInput.v1",
        "required": {"source": bindings["acceptedRollout"]["source"], "rows": [{"id": OBLIGATION_ID, "contract": required}]},
        "provided": {"source": bindings["retainedArtifact"]["source"], "rows": [{"id": OBLIGATION_ID, "contract": required, "evidence_refs": {ROLE: receipt_id}}]},
        "observations": {"source": bindings["observer"]["source"], "rows": [{"id": OBLIGATION_ID, "attempt": target_candidate, "epoch": EPOCH, "refs": {ROLE: receipt_id}}]},
        "receipts": {"source": bindings["independentJudgment"]["source"], "rows": [receipt]},
    }
    admission = {
        "kind": "contractDiffAdmission.v1",
        "scope": {"id": "logger-language-neutral-establishment", "authority": bindings["acceptedDecision"]["source"], "epoch": EPOCH, "allow_empty": False, "grade": "source", "excluded_ids": []},
        "universe": [{"id": OBLIGATION_ID, "obligation_digest": required["obligation_digest"], "profile": required["profile"]}],
        "inventory": {},
        "evidence": {receipt_id: _digest(receipt)},
    }
    for name in ("required", "provided", "observations", "receipts"):
        rows = sorted(packet[name]["rows"], key=lambda row: row["id"])
        admission["inventory"][name] = {"source": packet[name]["source"], "rows_digest": _digest(rows), "count": len(rows)}
    _write(bundle / "contract-diff-input.json", packet)
    _write(bundle / "contract-diff-admission.json", admission)
    cli = runtime_source / SOURCE_PATHS["comparatorCli"]
    code, positive = _compare(cli, bundle / "contract-diff-input.json", bundle / "contract-diff-admission.json", runtime_source)
    _need(code == 0 and positive.get("status") == "CLOSED" and positive.get("findings") == [], "positive", positive)
    _write(bundle / "contract-diff-positive.json", positive)
    cases: dict[str, tuple[dict[str, Any], dict[str, Any], str]] = {}
    drift = copy.deepcopy(packet); drift["provided"]["rows"][0]["contract"]["target"]["resource"] = "wrong-logger-design"
    drift_admission = copy.deepcopy(admission)
    rows = sorted(drift["provided"]["rows"], key=lambda row: row["id"]); drift_admission["inventory"]["provided"] = {"source": drift["provided"]["source"], "rows_digest": _digest(rows), "count": len(rows)}
    cases["contract-drift"] = (drift, drift_admission, "OPEN")
    missing = copy.deepcopy(packet); missing["observations"]["rows"] = []
    missing_admission = copy.deepcopy(admission); missing_admission["inventory"]["observations"] = {"source": missing["observations"]["source"], "rows_digest": _digest([]), "count": 0}
    cases["missing-observation"] = (missing, missing_admission, "OPEN")
    stale = copy.deepcopy(packet); stale["observations"]["rows"][0]["attempt"] = "0" * 40
    stale_admission = copy.deepcopy(admission); rows = sorted(stale["observations"]["rows"], key=lambda row: row["id"]); stale_admission["inventory"]["observations"] = {"source": stale["observations"]["source"], "rows_digest": _digest(rows), "count": len(rows)}
    cases["wrong-candidate"] = (stale, stale_admission, "OPEN")
    cases["missing-admission"] = (packet, {}, "UNKNOWN")
    for name, (bad_packet, bad_admission, expected) in cases.items():
        packet_path = bundle / f"negative-{name}-input.json"; admission_path = bundle / f"negative-{name}-admission.json"
        _write(packet_path, bad_packet); _write(admission_path, bad_admission)
        exit_code, result = _compare(cli, packet_path, admission_path, runtime_source)
        _need(exit_code == STATUS_EXIT[expected] and result.get("status") == expected, "negative", {"case": name, "exit": exit_code, "result": result})
        _write(bundle / f"contract-diff-negative-{name}.json", result)

    scope = {
        "kind": "governance.loggerLanguageNeutralEstablishmentScope.v1",
        "authority": False,
        "scopeId": "logger-language-neutral-establishment",
        "selectedObligations": [OBLIGATION_ID],
        SCOPE_CANDIDATE_FIELD: target_candidate,
        "subjectKey": SUBJECT_KEY,
        "governanceRevision": "692013f50581437fb9004cdedafedbb4a7a271de",
        "acceptedRequirementDigest": required["obligation_digest"],
        "requiredEvidenceTypes": [ROLE],
    }
    _write(bundle / "run-scope.json", scope)
    evidence = expected_evidence(scope=scope, sources={key: value["source"] for key, value in bindings.items()}, bindings=bindings, bundle=bundle, receipt_rows=[receipt], read_object=lambda path, label: _read(path), sha256_file=_sha_file, digest=_digest, required_contract=required)
    _write(bundle / "phase4-evidence.json", evidence)
    manifest = [{"path": path.relative_to(bundle).as_posix(), "sha256": _sha_file(path)} for path in sorted(bundle.rglob("*")) if path.is_file() and path.name != "bundle-manifest.json"]
    _write(bundle / "bundle-manifest.json", manifest)
    return {"kind": "governance.packageContractTargetMaterials.v1", "targetId": TARGET_ID, "bundle": str(bundle), "producerFiles": ["logger-k-readback.json", "logger-cold-selection.json"], "authority": False}
