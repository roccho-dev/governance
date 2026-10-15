from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from tools.package_contract_port_common import *


def verify_bundle(
    bundle: Path,
    target_source: Path,
    target_candidate: str,
    accepted_requirement_source: Path,
    target_id: str = "ops",
    governance_candidate: str | None = None,
    governance_policy_source: Path | None = None,
    contract_runtime_source: Path | None = None,
    evidence_input: Path | None = None,
) -> dict[str, Any]:
    module, binding, identity = load_target(target_id)
    bundle = bundle.resolve()
    target_source = target_source.resolve()
    accepted_requirement_source = accepted_requirement_source.resolve()
    policy_source = governance_policy_source.resolve() if governance_policy_source else accepted_requirement_source
    runtime_identity = binding["contractRuntimeSource"]
    runtime_source = contract_runtime_source.resolve() if contract_runtime_source else None
    if (
        runtime_source is None
        and runtime_identity["repository"] == binding["targetSource"]["repository"]
        and runtime_identity["revision"] == target_candidate
    ):
        runtime_source = target_source

    need(HEX40.fullmatch(target_candidate) is not None, "target-candidate")
    need(isinstance(governance_candidate, str) and HEX40.fullmatch(governance_candidate) is not None, "governance-candidate")
    need(target_candidate == binding["targetSource"]["revision"], "target-binding-candidate")
    verify_git_head(target_source, target_candidate, "target-source")
    verify_git_head(accepted_requirement_source, binding["acceptedRequirementSource"]["revision"], "accepted-requirement-source")
    verify_git_head(policy_source, binding["governancePolicySource"]["revision"], "governance-policy-source")
    need(runtime_source is not None, "contract-runtime-root")
    verify_git_head(runtime_source, runtime_identity["revision"], "contract-runtime-source")
    evidence_identity = verify_evidence_input(evidence_input, binding, target_id, target_candidate)
    verify_manifest(bundle)

    bindings = read_object(bundle / "source-bindings.json", "source-bindings")
    paths = module.SOURCE_PATHS
    roots = binding["sourceRoots"]
    accepted_files = module.ACCEPTED_FILES
    need(set(bindings) == set(paths) | set(accepted_files) | {"observer"}, "source-binding-universe")
    sources: dict[str, dict[str, Any]] = {}
    target_native = runtime_count = 0
    for role, relative in paths.items():
        if roots[role] == "target":
            repository, revision = binding["providerRepository"], target_candidate
            native, expected_blob = target_source / relative, None
            target_native += 1
        else:
            spec = runtime_identity["allowedPaths"][role]
            repository, revision = runtime_identity["repository"], runtime_identity["revision"]
            native = runtime_source / relative
            expected_blob = spec["gitBlob"]
            runtime_count += 1
        sources[role] = verify_source_binding(bindings, role, repository, revision, relative, native, bundle, expected_blob)

    observer = verify_source_binding(
        bindings,
        "observer",
        "roccho-dev/governance",
        governance_candidate,
        identity["adapterPath"],
        ROOT / identity["adapterPath"],
        bundle,
    )
    allowed = binding["acceptedRequirementSource"]["allowedPaths"]
    need(set(allowed) == set(accepted_files), "accepted-path-universe")
    accepted: dict[str, dict[str, Any]] = {}
    for role, relative in accepted_files.items():
        spec = allowed[role]
        need(spec.get("path") == relative, "accepted-path:" + role)
        accepted[role] = verify_source_binding(
            bindings,
            role,
            binding["acceptedRequirementSource"]["repository"],
            binding["acceptedRequirementSource"]["revision"],
            relative,
            accepted_requirement_source / relative,
            bundle,
            spec.get("gitBlob"),
        )

    source_count = len(paths) + len(accepted_files) + 1
    lower = binding["lowerVerifier"]
    lower_mode, lower_path, lower_digest = "common-reconstruction", None, None
    if lower["mode"] == "required":
        role = lower["sourceRole"]
        lower_path, lower_digest = paths[role], sources[role]["digest"]
        native_root = target_source if roots[role] == "target" else runtime_source
        process = run([sys.executable, str(native_root / lower_path), "verify", "--bundle", str(bundle)], native_root)
        need(process.returncode == 0 and process.stdout.strip() != "", "verifier-execution")
        verified = json.loads(process.stdout)
        need(verified.get("status") == "PASS", "verifier-status")
        need(verified.get("authority") is False and verified.get("adoption") is False, "verifier-authority")
        need(verified.get("releasePublished") is False and verified.get("remaining") == 0, "verifier-boundary")
        need(verified.get("claimCeiling") == binding["claimCeiling"], "verifier-ceiling")
        fields = module.LOWER_FIELDS
        need(verified.get(fields["candidate"]) == target_candidate, "verifier-candidate")
        need(verified.get(fields["acceptedRevision"]) == binding["acceptedRequirementSource"]["revision"], "verifier-accepted-revision")
        need(verified.get(fields["observerRevision"]) == governance_candidate, "verifier-observer-revision")
        need(verified.get("sourceBytesVerified") == source_count, "verifier-source-count")
        need(
            verified.get("receiptReplayed") is True
            and verified.get("comparatorReplayed") is True
            and verified.get("evidenceBound") is True,
            "verifier-replay",
        )
        lower_mode = "target-verifier+common-reconstruction"

    scope_path, evidence_path = bundle / "run-scope.json", bundle / "phase4-evidence.json"
    scope, evidence = read_object(scope_path, "scope"), read_object(evidence_path, "evidence")
    need(scope.get("selectedObligations") == [binding["obligationId"]], "scope-obligation")
    need(scope.get(module.SCOPE_CANDIDATE_FIELD) == target_candidate, "scope-candidate")
    need(scope.get("governanceRevision") == binding["governancePolicySource"]["revision"], "scope-governance")
    need(scope.get("authority") is False, "scope-authority")

    decision = read_object(accepted_requirement_source / accepted_files["acceptedDecision"], "accepted-decision")
    rollout = read_object(accepted_requirement_source / accepted_files["acceptedRollout"], "accepted-rollout")
    _, required_contract = module.required_contract(decision, rollout, digest, check_token)
    need(scope.get("acceptedRequirementDigest") == required_contract["obligation_digest"], "scope-accepted-reconstruction")

    packet = read_object(bundle / "contract-diff-input.json", "contract-diff-input")
    required_role = getattr(module, "REQUIRED_SOURCE_ROLE", "acceptedRollout")
    provided_role = getattr(module, "PROVIDED_SOURCE_ROLE", "providerClaim")
    receipt_role = getattr(module, "RECEIPT_SOURCE_ROLE", "receiptProducer")
    need(packet.get("required", {}).get("rows") == [{"id": binding["obligationId"], "contract": required_contract}], "packet-required-reconstruction")
    need(packet.get("required", {}).get("source") == accepted[required_role], "packet-required-source")
    need(packet.get("provided", {}).get("source") == sources[provided_role], "packet-provider-source")
    need(packet.get("observations", {}).get("source") == observer, "packet-observer-source")
    need(packet.get("receipts", {}).get("source") == sources[receipt_role], "packet-receipt-source")
    receipt_rows = packet.get("receipts", {}).get("rows")
    need(isinstance(receipt_rows, list) and len(receipt_rows) == 1 and isinstance(receipt_rows[0], dict), "packet-receipt-row")
    receipt = receipt_rows[0]
    executor = binding["evidenceExecutor"]
    need(receipt.get("obligation_id") == binding["obligationId"], "receipt-obligation")
    need(receipt.get("operation") == executor["operation"], "receipt-operation")
    need(receipt.get("grade") == executor["grade"], "receipt-grade")
    need(receipt.get("status") == "PASS", "receipt-status")
    if executor["readback"]:
        need(receipt.get("readback") == "PASS", "receipt-readback")

    combined = {**sources, **accepted, "observer": observer}
    reconstructed = module.expected_evidence(
        scope=scope,
        sources=combined,
        bindings=bindings,
        bundle=bundle,
        receipt_rows=receipt_rows,
        read_object=read_object,
        sha256_file=sha256_file,
        digest=digest,
        required_contract=required_contract,
    )
    need(evidence == reconstructed, "evidence-reconstruction")
    positive, negative, exits = replay_comparator(bundle, bindings, paths)
    need(positive.get("status") == "CLOSED" and positive.get("findings") == [], "positive")
    need({k: v.get("status") for k, v in negative.items()} == REQUIRED_NEGATIVE, "negative")

    member = {
        "kind": "governance.packageContractClosureMember.v3",
        "status": "pass",
        "authority": False,
        "adoption": False,
        "releasePublished": False,
        "claimCeiling": binding["claimCeiling"],
        "targetId": target_id,
        "logicalRepository": binding["logicalRepository"],
        "providerRepository": binding["providerRepository"],
        "scopeId": scope.get("scopeId"),
        "obligationId": binding["obligationId"],
        "targetCandidate": target_candidate,
        "governanceCandidate": governance_candidate,
        "acceptedRequirementDigest": required_contract["obligation_digest"],
        "acceptedRequirementRevision": binding["acceptedRequirementSource"]["revision"],
        "governancePolicyRevision": binding["governancePolicySource"]["revision"],
        "contractRuntimeRepository": runtime_identity["repository"],
        "contractRuntimeRevision": runtime_identity["revision"],
        "contractDiffStatus": positive["status"],
        "contractDiffExit": exits["positive"],
        "negativeStatus": REQUIRED_NEGATIVE,
        "negativeExit": {name: exits[name] for name in REQUIRED_NEGATIVE},
        "scopeDigest": sha256_file(scope_path),
        "evidenceDigest": sha256_file(evidence_path),
        "evidenceInputVerified": True,
        "evidenceInputMode": evidence_identity["mode"],
        "evidenceInputDigest": evidence_identity["digest"],
        "evidenceInputFilesVerified": evidence_identity["filesVerified"],
        "evidenceExecutor": evidence_identity["executor"],
        "remaining": 0,
        "evidenceBound": True,
        "observerMeaningVerified": True,
        "evidenceReconstructed": True,
        "targetSourceClosureVerified": True,
        "targetSourcesVerified": len(paths),
        "targetNativeSourcesVerified": target_native,
        "runtimeSourcesVerified": runtime_count,
        "sourceBytesVerified": source_count,
        "receiptReplayed": True,
        "comparatorReplayed": True,
        "lowerProofMode": lower_mode,
        "lowerVerifierPath": lower_path,
        "lowerVerifierDigest": lower_digest,
        "adapterPath": identity["adapterPath"],
        "adapterDigest": identity["adapterDigest"],
        "targetBindingPath": identity["targetBindingPath"],
        "targetBindingDigest": identity["targetBindingDigest"],
        "commonCheckerPath": COMMON_CHECKER_PATH,
        "commonCheckerDigest": sha256_file(ROOT / COMMON_CHECKER_PATH),
        "bundleManifestDigest": sha256_file(bundle / "bundle-manifest.json"),
    }
    member["memberDigest"] = sha256_bytes(canonical(member).encode())
    return member
