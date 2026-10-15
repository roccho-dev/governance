from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.package_contract_port_common import *
from tools.package_contract_port_verify import verify_bundle


def produce_bundle(
    *,
    target_id: str,
    bundle: Path,
    target_source: Path,
    accepted_requirement_source: Path,
    governance_policy_source: Path,
    governance_candidate: str,
    contract_runtime_source: Path | None = None,
    evidence_input: Path | None = None,
) -> dict[str, Any]:
    module, binding, identity = load_target(target_id)
    target_source = target_source.resolve()
    accepted_requirement_source = accepted_requirement_source.resolve()
    governance_policy_source = governance_policy_source.resolve()
    verify_git_head(target_source, binding["targetSource"]["revision"], "target-source")
    verify_git_head(accepted_requirement_source, binding["acceptedRequirementSource"]["revision"], "accepted-requirement-source")
    verify_git_head(governance_policy_source, binding["governancePolicySource"]["revision"], "governance-policy-source")
    if contract_runtime_source is not None:
        contract_runtime_source = contract_runtime_source.resolve()
        verify_git_head(contract_runtime_source, binding["contractRuntimeSource"]["revision"], "contract-runtime-source")
    verify_evidence_input(evidence_input, binding, target_id, binding["targetSource"]["revision"])
    context = {
        "bundle": str(bundle.resolve()),
        "targetSourceRoot": str(target_source),
        "acceptedRequirementRoot": str(accepted_requirement_source),
        "governancePolicyRoot": str(governance_policy_source),
        "contractRuntimeRoot": str(contract_runtime_source) if contract_runtime_source else "",
        "evidenceInputRoot": str(evidence_input.resolve()) if evidence_input else "",
        "evidenceExecutor": binding["evidenceExecutor"],
        "targetCandidate": binding["targetSource"]["revision"],
        "acceptedRequirementRevision": binding["acceptedRequirementSource"]["revision"],
        "governanceCandidate": governance_candidate,
        "observerRoot": str(ROOT),
        "adapterPath": identity["adapterPath"],
    }
    result = module.produce(context)
    need(
        isinstance(result, dict)
        and result.get("targetId") == target_id
        and result.get("authority") is False,
        "target-materials",
    )
    return result


def cross_target_preflight(
    target_source: Path,
    runtime_source: Path,
    accepted_source: Path,
    evidence_input: Path,
) -> dict[str, Any]:
    target_head = "71409fa013b6cb681c0a80b4c377e4685685b690"
    runtime_head = "5eb98c82417b399978c1e38aebab5e3fb39752d4"
    accepted_head = "862313008ad19a743034599792d9a8b6e470e4cf"
    verify_git_head(target_source, target_head, "preflight-target")
    verify_git_head(runtime_source, runtime_head, "preflight-runtime")
    verify_git_head(accepted_source, accepted_head, "preflight-accepted")
    artifact_path = target_source / "packages/voice-ui/artifact.jsonl"
    artifact_rows = [line for line in artifact_path.read_text(encoding="utf-8").splitlines() if line]
    need(len(artifact_rows) == 1, "preflight-artifact-row")
    artifact = json.loads(artifact_rows[0])
    need(
        artifact == {"artifact": "voice-ui", "kind": "artifact.auth.v1", "requiredCapabilities": ["jev-api"]},
        "preflight-artifact",
    )
    need(not (target_source / "packages/contract-diff/bin/contract-diff.py").exists(), "preflight-target-comparator-absent")
    need(not (target_source / "tools/contract-632-phase4-bind.py").exists(), "preflight-target-binder-absent")
    runtime_cli = runtime_source / "packages/contract-diff/bin/contract-diff.py"
    runtime_core = runtime_source / "packages/contract-diff/core.py"
    need(git_blob_file(runtime_cli) == "e06a74b4323f2772fbbb69fac9ba543c4326b97b", "preflight-runtime-cli")
    need(git_blob_file(runtime_core) == "9613c92deb6ee12b335863a36261268976ad9cc5", "preflight-runtime-core")
    runtime_selftest = run([sys.executable, str(runtime_cli), "--selftest"], runtime_source)
    if runtime_selftest.returncode != 0:
        raise ValueError(
            "package-contract-bundle:preflight-runtime-selftest:"
            + json.dumps(
                {
                    "exit": runtime_selftest.returncode,
                    "stdout": runtime_selftest.stdout[-12000:],
                    "stderr": runtime_selftest.stderr[-12000:],
                },
                sort_keys=True,
            )
        )
    requirement_path = accepted_source / "decisions/apps-voice-ui-artifact-auth-requirement-261015.jsonl"
    rows = [json.loads(line) for line in requirement_path.read_text(encoding="utf-8").splitlines() if line]
    need(len(rows) == 1, "preflight-requirement-row")
    row = rows[0]
    meaning = row.get("meaning_identity", {})
    need(row.get("subject_key") == "package:apps/voice-ui-artifact-auth", "preflight-subject")
    need(meaning.get("declaration") == artifact, "preflight-declaration")
    need(
        meaning.get("mandatory_profile")
        == [{"grade": "source", "operation": "nix-build-voice-ui-dist", "readback": True, "role": "artifact-build-readback"}],
        "preflight-profile",
    )
    projection = row.get("apps_source_binding", {}).get("projection", {})
    need(
        projection.get("build_target") == "voice-ui-dist"
        and projection.get("output_path") == ".envs/artifact.jsonl",
        "preflight-projection",
    )
    preflight_binding = {
        "targetId": "apps-shape-preflight",
        "targetSource": {"revision": target_head},
        "evidenceExecutor": {
            "kind": "exact-existing-release",
            "operation": "nix-build-voice-ui-dist",
            "readback": True,
            "grade": "source",
        },
    }
    evidence = verify_evidence_input(evidence_input, preflight_binding, "apps-shape-preflight", target_head)
    need(evidence["mode"] == "exact-existing-release", "preflight-evidence-mode")
    need(evidence["receipt"] is not None, "preflight-evidence-receipt")
    return {
        "kind": "governance.contract632.crossTargetPortPreflight.v2",
        "status": "pass",
        "authority": False,
        "memberCreated": False,
        "targetRepository": "roccho-dev/apps",
        "targetRevision": target_head,
        "targetArtifactDigest": sha256_file(artifact_path),
        "contractRuntimeRepository": "roccho-org/ops",
        "contractRuntimeRevision": runtime_head,
        "runtimeCliDigest": sha256_file(runtime_cli),
        "runtimeCoreDigest": sha256_file(runtime_core),
        "runtimeComparatorSelftest": True,
        "acceptedRequirementRepository": "roccho-dev/adrs",
        "acceptedRequirementRevision": accepted_head,
        "acceptedRequirementDigest": sha256_file(requirement_path),
        "targetRuntimeSeparated": True,
        "targetLocalComparatorPresent": False,
        "targetLocalLowerVerifierPresent": False,
        "lowerVerifierMayBeNone": True,
        "evidenceOperation": "nix-build-voice-ui-dist",
        "evidenceInputVerified": True,
        "evidenceInputDigest": evidence["digest"],
        "evidenceInputFilesVerified": evidence["filesVerified"],
        "sourceOutputBytesEqual": True,
        "claimCeiling": "APPS_ARTIFACT_DECLARATION_AND_EXACT_BUILD_PROJECTION_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        nargs="?",
        choices=["discover", "plan", "produce", "check", "preflight"],
        default="check",
    )
    parser.add_argument("--target-id")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--target-source", type=Path)
    parser.add_argument("--target-candidate")
    parser.add_argument("--accepted-requirement-source", type=Path)
    parser.add_argument("--governance-policy-source", type=Path)
    parser.add_argument("--contract-runtime-source", type=Path)
    parser.add_argument("--evidence-input", type=Path)
    parser.add_argument("--governance-candidate")
    parser.add_argument("--preflight-target-source", type=Path)
    parser.add_argument("--preflight-runtime-source", type=Path)
    parser.add_argument("--preflight-accepted-source", type=Path)
    parser.add_argument("--preflight-evidence-input", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.command == "discover":
        report = {"kind": "governance.packageContractTargets.v1", "targets": discover_targets()}
    elif args.command == "preflight":
        roots = (
            args.preflight_target_source,
            args.preflight_runtime_source,
            args.preflight_accepted_source,
            args.preflight_evidence_input,
        )
        if any(root is None for root in roots):
            parser.error("preflight requires target, runtime, accepted and evidence roots")
        report = cross_target_preflight(*roots)
    else:
        if not args.target_id:
            parser.error("--target-id is required")
        if args.command == "plan":
            _, binding, identity = load_target(args.target_id)
            report = {"binding": binding, "identity": identity}
        else:
            required = (
                args.bundle,
                args.target_source,
                args.accepted_requirement_source,
                args.governance_policy_source,
                args.contract_runtime_source,
                args.evidence_input,
                args.governance_candidate,
            )
            if any(value is None for value in required):
                parser.error("produce/check require bundle, target, accepted, policy, runtime, evidence and Governance candidate")
            _, binding, _ = load_target(args.target_id)
            if args.command == "produce":
                report = produce_bundle(
                    target_id=args.target_id,
                    bundle=args.bundle,
                    target_source=args.target_source,
                    accepted_requirement_source=args.accepted_requirement_source,
                    governance_policy_source=args.governance_policy_source,
                    governance_candidate=args.governance_candidate,
                    contract_runtime_source=args.contract_runtime_source,
                    evidence_input=args.evidence_input,
                )
            else:
                report = verify_bundle(
                    args.bundle,
                    args.target_source,
                    args.target_candidate or binding["targetSource"]["revision"],
                    args.accepted_requirement_source,
                    args.target_id,
                    args.governance_candidate,
                    args.governance_policy_source,
                    args.contract_runtime_source,
                    args.evidence_input,
                )
    text = canonical(report) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
