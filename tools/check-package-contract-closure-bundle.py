#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "tools/package_contract_targets"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
TARGET_ID = re.compile(r"^[a-z][a-z0-9-]*$")
STATUS_EXIT = {"CLOSED": 0, "OPEN": 2, "INVALID": 3, "UNKNOWN": 4}
REQUIRED_NEGATIVE = {
    "contract-drift": "OPEN",
    "missing-observation": "OPEN",
    "wrong-candidate": "OPEN",
    "missing-admission": "UNKNOWN",
}
COMMON_CHECKER_PATH = "tools/check-package-contract-closure-bundle.py"


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob_file(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def digest(value: Any) -> str:
    return sha256_bytes(canonical(value).encode())


def read_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(label + "-not-object")
    return value


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("package-contract-bundle:" + code)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def check_token(value: str) -> str:
    token = value.replace(" / ", "/").replace(" ", "")
    need(token != "" and " " not in token, "check-token")
    return token


def _inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def validate_provider_relation(binding: dict[str, Any]) -> None:
    target = binding.get("targetSource")
    need(isinstance(target, dict), "target-source-binding")
    target_repository = target.get("repository")
    provider_repository = binding.get("providerRepository")
    need(
        isinstance(target_repository, str) and target_repository != "",
        "target-source-repository",
    )
    need(
        isinstance(provider_repository, str) and provider_repository != "",
        "provider-repository",
    )
    if target_repository == provider_repository:
        return
    alias = binding.get("providerAlias")
    need(isinstance(alias, dict), "target-provider-relation")
    need(
        alias
        == {
            "logicalRepository": binding.get("logicalRepository"),
            "providerRepository": provider_repository,
            "targetRepository": target_repository,
            "relation": "current-provider-for-logical-contract",
            "authority": False,
        },
        "target-provider-relation",
    )


def target_paths(target_id: str) -> tuple[Path, Path]:
    need(TARGET_ID.fullmatch(target_id) is not None, "target-id")
    adapter = TARGET_DIR / f"{target_id}.py"
    binding = TARGET_DIR / f"{target_id}.target.json"
    need(_inside_root(adapter) and _inside_root(binding), "target-path")
    need(adapter.is_file() and not adapter.is_symlink(), "adapter-file")
    need(binding.is_file() and not binding.is_symlink(), "target-binding-file")
    return adapter, binding


def load_target(target_id: str) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    adapter_path, binding_path = target_paths(target_id)
    binding = read_object(binding_path, "target-binding")
    need(binding.get("kind") == "governance.packageContractTarget.v1", "target-binding-kind")
    need(binding.get("targetId") == target_id, "target-binding-id")
    expected_adapter = adapter_path.relative_to(ROOT).as_posix()
    need(binding.get("adapterPath") == expected_adapter, "target-binding-adapter")
    validate_provider_relation(binding)
    spec = importlib.util.spec_from_file_location(
        f"package_contract_target_{target_id}", adapter_path
    )
    need(spec is not None and spec.loader is not None, "adapter-import")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    description = module.describe()
    need(isinstance(description, dict), "adapter-description")
    for key in (
        "targetId",
        "logicalRepository",
        "providerRepository",
        "claimCeiling",
        "obligationId",
    ):
        need(description.get(key) == binding.get(key), "adapter-binding:" + key)
    need(description.get("statusExit") == STATUS_EXIT, "adapter-status-exit")
    need(
        getattr(module, "EXPECTED_NEGATIVE", None) == REQUIRED_NEGATIVE,
        "adapter-negative-contract",
    )
    return module, binding, {
        "adapterPath": expected_adapter,
        "adapterDigest": sha256_file(adapter_path),
        "targetBindingPath": binding_path.relative_to(ROOT).as_posix(),
        "targetBindingDigest": sha256_file(binding_path),
    }


def discover_targets() -> list[str]:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    py_ids = {
        path.stem
        for path in TARGET_DIR.glob("*.py")
        if path.name != "__init__.py"
    }
    json_ids = {
        path.name[: -len(".target.json")]
        for path in TARGET_DIR.glob("*.target.json")
    }
    need(py_ids == json_ids, "adapter-binding-set")
    targets = sorted(py_ids)
    need(len(targets) == len(set(targets)), "duplicate-target-id")
    for target_id in targets:
        load_target(target_id)
    return targets


def verify_git_head(root: Path, expected: str, label: str) -> None:
    need(root.is_dir(), label + "-root")
    process = run(["git", "rev-parse", "HEAD"], root)
    need(process.returncode == 0, label + "-git-head")
    need(process.stdout.strip() == expected, label + "-revision")


def verify_source_binding(
    bindings: dict[str, Any],
    key: str,
    repository: str,
    revision: str,
    source_path: str,
    native: Path,
    bundle: Path,
    expected_git_blob: str | None = None,
) -> dict[str, Any]:
    row = bindings.get(key)
    need(isinstance(row, dict), "source-binding:" + key)
    source = row.get("source")
    need(isinstance(source, dict), "source-descriptor:" + key)
    need(source.get("repository") == repository, "source-repository:" + key)
    need(source.get("revision") == revision, "source-revision:" + key)
    need(source.get("path") == source_path, "source-path:" + key)

    bundle_path = row.get("bundlePath")
    need(
        isinstance(bundle_path, str) and bundle_path != "",
        "source-bundle-path:" + key,
    )
    carried = bundle / bundle_path
    need(native.is_file() and not native.is_symlink(), "source-native:" + key)
    need(carried.is_file() and not carried.is_symlink(), "source-carried:" + key)
    need(carried.read_bytes() == native.read_bytes(), "source-bytes:" + key)
    need(source.get("digest") == sha256_file(native), "source-digest:" + key)
    if expected_git_blob is not None:
        need(git_blob_file(native) == expected_git_blob, "source-git-blob:" + key)
    return source


def replay_comparator(
    bundle: Path,
    target_source: Path,
    cli_path: str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, int]]:
    cli = target_source / cli_path

    def one(input_path: Path, admission_path: Path, result_path: Path, label: str):
        process = run(
            [
                sys.executable,
                str(cli),
                "--input",
                str(input_path),
                "--admission",
                str(admission_path),
            ],
            target_source,
        )
        need(process.stdout.strip() != "", "comparator-output:" + label)
        actual = json.loads(process.stdout)
        stored = read_object(result_path, "comparator-result:" + label)
        need(actual == stored, "comparator-result:" + label)
        status = actual.get("status")
        need(status in STATUS_EXIT, "comparator-status:" + label)
        need(process.returncode == STATUS_EXIT[status], "comparator-exit:" + label)
        return actual, process.returncode

    positive, positive_exit = one(
        bundle / "contract-diff-input.json",
        bundle / "contract-diff-admission.json",
        bundle / "contract-diff-positive.json",
        "positive",
    )
    negative: dict[str, dict[str, Any]] = {}
    exits = {"positive": positive_exit}
    for name, expected in REQUIRED_NEGATIVE.items():
        result, code = one(
            bundle / f"negative-{name}-input.json",
            bundle / f"negative-{name}-admission.json",
            bundle / f"contract-diff-negative-{name}.json",
            name,
        )
        need(result.get("status") == expected, "negative-status:" + name)
        negative[name] = result
        exits[name] = code
    return positive, negative, exits


def verify_bundle(
    bundle: Path,
    target_source: Path,
    target_candidate: str,
    accepted_requirement_source: Path,
    target_id: str = "ops",
    governance_candidate: str | None = None,
    governance_policy_source: Path | None = None,
) -> dict[str, Any]:
    module, binding, target_identity = load_target(target_id)
    bundle = bundle.resolve()
    target_source = target_source.resolve()
    accepted_requirement_source = accepted_requirement_source.resolve()
    governance_policy_source = (
        governance_policy_source.resolve()
        if governance_policy_source is not None
        else accepted_requirement_source
    )

    need(HEX40.fullmatch(target_candidate) is not None, "target-candidate")
    need(
        isinstance(governance_candidate, str)
        and HEX40.fullmatch(governance_candidate) is not None,
        "governance-candidate",
    )
    need(bundle.is_dir(), "bundle")
    need(
        target_candidate == binding["targetSource"]["revision"],
        "target-binding-candidate",
    )
    verify_git_head(target_source, target_candidate, "target-source")
    verify_git_head(
        accepted_requirement_source,
        binding["acceptedRequirementSource"]["revision"],
        "accepted-requirement-source",
    )
    verify_git_head(
        governance_policy_source,
        binding["governancePolicySource"]["revision"],
        "governance-policy-source",
    )

    bindings = read_object(bundle / "source-bindings.json", "source-bindings")
    source_paths = module.SOURCE_PATHS
    accepted_files = module.ACCEPTED_FILES
    expected_source_roles = set(source_paths) | set(accepted_files) | {"observer"}
    need(set(bindings) == expected_source_roles, "source-binding-universe")
    target_sources: dict[str, dict[str, Any]] = {}
    for key, relative in source_paths.items():
        target_sources[key] = verify_source_binding(
            bindings,
            key,
            binding["providerRepository"],
            target_candidate,
            relative,
            target_source / relative,
            bundle,
        )

    adapter_path = ROOT / target_identity["adapterPath"]
    observer_source = verify_source_binding(
        bindings,
        "observer",
        "roccho-dev/governance",
        governance_candidate,
        target_identity["adapterPath"],
        adapter_path,
        bundle,
    )
    verifier_path = module.LOWER_VERIFIER_PATH
    verifier_source = target_sources["binder"]
    process = run(
        [
            sys.executable,
            str(target_source / verifier_path),
            "verify",
            "--bundle",
            str(bundle),
        ],
        target_source,
    )
    need(
        process.returncode == 0 and process.stdout.strip() != "",
        "verifier-execution",
    )
    verified = json.loads(process.stdout)
    need(verified.get("status") == "PASS", "verifier-status")
    need(
        verified.get("authority") is False
        and verified.get("adoption") is False,
        "verifier-authority",
    )
    need(
        verified.get("releasePublished") is False
        and verified.get("remaining") == 0,
        "verifier-boundary",
    )
    need(
        verified.get("claimCeiling") == binding["claimCeiling"],
        "verifier-ceiling",
    )
    lower_fields = module.LOWER_FIELDS
    need(
        verified.get(lower_fields["candidate"]) == target_candidate,
        "verifier-candidate",
    )
    need(
        verified.get(lower_fields["acceptedRevision"])
        == binding["acceptedRequirementSource"]["revision"],
        "verifier-accepted-revision",
    )
    need(
        verified.get(lower_fields["observerRevision"]) == governance_candidate,
        "verifier-observer-revision",
    )
    need(
        verified.get("sourceBytesVerified")
        == binding["expectedSourceBytesVerified"],
        "verifier-source-count",
    )
    need(
        verified.get("receiptReplayed") is True
        and verified.get("comparatorReplayed") is True,
        "verifier-replay",
    )
    need(verified.get("evidenceBound") is True, "verifier-evidence-bound")

    allowed = binding["acceptedRequirementSource"]["allowedPaths"]
    need(set(allowed) == set(accepted_files), "accepted-path-universe")
    accepted_sources: dict[str, dict[str, Any]] = {}
    for key, relative in accepted_files.items():
        spec = allowed.get(key)
        need(isinstance(spec, dict), "accepted-path-binding:" + key)
        need(spec.get("path") == relative, "accepted-path:" + key)
        accepted_sources[key] = verify_source_binding(
            bindings,
            key,
            binding["acceptedRequirementSource"]["repository"],
            binding["acceptedRequirementSource"]["revision"],
            relative,
            accepted_requirement_source / relative,
            bundle,
            spec.get("gitBlob"),
        )

    scope_path = bundle / "run-scope.json"
    evidence_path = bundle / "phase4-evidence.json"
    scope = read_object(scope_path, "scope")
    evidence = read_object(evidence_path, "evidence")
    need(
        scope.get("selectedObligations") == [binding["obligationId"]],
        "scope-obligation",
    )
    need(
        scope.get(module.SCOPE_CANDIDATE_FIELD) == target_candidate,
        "scope-candidate",
    )
    need(
        scope.get("governanceRevision")
        == binding["governancePolicySource"]["revision"],
        "scope-governance",
    )
    need(scope.get("authority") is False, "scope-authority")

    decision = read_object(
        accepted_requirement_source / accepted_files["acceptedDecision"],
        "accepted-decision",
    )
    rollout = read_object(
        accepted_requirement_source / accepted_files["acceptedRollout"],
        "accepted-rollout",
    )
    _, required_contract = module.required_contract(
        decision, rollout, digest, check_token
    )
    need(
        scope.get("acceptedRequirementDigest")
        == required_contract["obligation_digest"],
        "scope-accepted-reconstruction",
    )

    packet = read_object(bundle / "contract-diff-input.json", "contract-diff-input")
    need(
        packet.get("required", {}).get("rows")
        == [{"id": binding["obligationId"], "contract": required_contract}],
        "packet-required-reconstruction",
    )
    need(
        packet.get("required", {}).get("source")
        == accepted_sources["acceptedRollout"],
        "packet-required-source",
    )
    need(
        packet.get("provided", {}).get("source")
        == target_sources["providerClaim"],
        "packet-provider-source",
    )
    need(
        packet.get("observations", {}).get("source") == observer_source,
        "packet-observer-source",
    )
    need(
        packet.get("receipts", {}).get("source")
        == target_sources["receiptProducer"],
        "packet-receipt-source",
    )
    receipt_rows = packet.get("receipts", {}).get("rows")
    need(
        isinstance(receipt_rows, list)
        and len(receipt_rows) == 1
        and isinstance(receipt_rows[0], dict),
        "packet-receipt-row",
    )

    sources = {
        **target_sources,
        **accepted_sources,
        "observer": observer_source,
    }
    expected_evidence = module.expected_evidence(
        scope=scope,
        sources=sources,
        bindings=bindings,
        bundle=bundle,
        receipt_rows=receipt_rows,
        read_object=read_object,
        sha256_file=sha256_file,
        digest=digest,
        required_contract=required_contract,
    )
    need(evidence == expected_evidence, "evidence-reconstruction")

    positive, negative, comparator_exit = replay_comparator(
        bundle,
        target_source,
        module.SOURCE_PATHS["comparatorCli"],
    )
    need(
        positive.get("status") == "CLOSED" and positive.get("findings") == [],
        "positive",
    )
    need(
        {key: value.get("status") for key, value in negative.items()}
        == REQUIRED_NEGATIVE,
        "negative",
    )
    need(
        verified.get("scopeDigest") == sha256_file(scope_path), "scope-digest"
    )
    need(
        verified.get("evidenceDigest") == sha256_file(evidence_path),
        "evidence-digest",
    )

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
        "acceptedRequirementRevision": binding["acceptedRequirementSource"][
            "revision"
        ],
        "governancePolicyRevision": binding["governancePolicySource"]["revision"],
        "contractDiffStatus": positive["status"],
        "contractDiffExit": comparator_exit["positive"],
        "negativeStatus": REQUIRED_NEGATIVE,
        "negativeExit": {
            name: comparator_exit[name] for name in REQUIRED_NEGATIVE
        },
        "scopeDigest": sha256_file(scope_path),
        "evidenceDigest": sha256_file(evidence_path),
        "remaining": 0,
        "evidenceBound": True,
        "observerMeaningVerified": True,
        "evidenceReconstructed": True,
        "targetSourceClosureVerified": True,
        "targetSourcesVerified": len(target_sources),
        "sourceBytesVerified": verified["sourceBytesVerified"],
        "receiptReplayed": True,
        "comparatorReplayed": True,
        "lowerVerifierPath": verifier_path,
        "lowerVerifierDigest": verifier_source["digest"],
        "adapterPath": target_identity["adapterPath"],
        "adapterDigest": target_identity["adapterDigest"],
        "targetBindingPath": target_identity["targetBindingPath"],
        "targetBindingDigest": target_identity["targetBindingDigest"],
        "commonCheckerPath": COMMON_CHECKER_PATH,
        "commonCheckerDigest": sha256_file(Path(__file__).resolve()),
        "bundleManifestDigest": sha256_file(bundle / "bundle-manifest.json"),
    }
    member["memberDigest"] = sha256_bytes(canonical(member).encode())
    return member


def produce_bundle(
    *,
    target_id: str,
    bundle: Path,
    target_source: Path,
    accepted_requirement_source: Path,
    governance_policy_source: Path,
    governance_candidate: str,
) -> dict[str, Any]:
    module, binding, target_identity = load_target(target_id)
    target_candidate = binding["targetSource"]["revision"]
    verify_git_head(target_source.resolve(), target_candidate, "target-source")
    verify_git_head(
        accepted_requirement_source.resolve(),
        binding["acceptedRequirementSource"]["revision"],
        "accepted-requirement-source",
    )
    verify_git_head(
        governance_policy_source.resolve(),
        binding["governancePolicySource"]["revision"],
        "governance-policy-source",
    )
    context = {
        "bundle": str(bundle.resolve()),
        "targetSourceRoot": str(target_source.resolve()),
        "acceptedRequirementRoot": str(accepted_requirement_source.resolve()),
        "governancePolicyRoot": str(governance_policy_source.resolve()),
        "targetCandidate": target_candidate,
        "acceptedRequirementRevision": binding["acceptedRequirementSource"][
            "revision"
        ],
        "governanceCandidate": governance_candidate,
        "observerRoot": str(ROOT),
        "adapterPath": target_identity["adapterPath"],
    }
    result = module.produce(context)
    need(
        isinstance(result, dict)
        and result.get("targetId") == target_id
        and result.get("authority") is False,
        "target-materials",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        nargs="?",
        choices=["discover", "plan", "produce", "check"],
        default="check",
    )
    parser.add_argument("--target-id")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--target-source", type=Path)
    parser.add_argument("--target-candidate")
    parser.add_argument("--accepted-requirement-source", type=Path)
    parser.add_argument("--governance-policy-source", type=Path)
    parser.add_argument("--governance-candidate")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    if args.command == "discover":
        print(canonical({"kind": "governance.packageContractTargets.v1", "targets": discover_targets()}))
        return 0
    if not args.target_id:
        parser.error("--target-id is required")
    if args.command == "plan":
        _, binding, identity = load_target(args.target_id)
        print(canonical({"binding": binding, "identity": identity}))
        return 0

    required = (
        args.bundle,
        args.target_source,
        args.accepted_requirement_source,
        args.governance_policy_source,
        args.governance_candidate,
    )
    if any(value is None for value in required):
        parser.error(
            "produce/check require --bundle, --target-source, "
            "--accepted-requirement-source, --governance-policy-source, "
            "and --governance-candidate"
        )
    _, binding, _ = load_target(args.target_id)
    target_candidate = args.target_candidate or binding["targetSource"]["revision"]
    if args.command == "produce":
        report = produce_bundle(
            target_id=args.target_id,
            bundle=args.bundle,
            target_source=args.target_source,
            accepted_requirement_source=args.accepted_requirement_source,
            governance_policy_source=args.governance_policy_source,
            governance_candidate=args.governance_candidate,
        )
    else:
        report = verify_bundle(
            args.bundle,
            args.target_source,
            target_candidate,
            args.accepted_requirement_source,
            args.target_id,
            args.governance_candidate,
            args.governance_policy_source,
        )
    text = canonical(report) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
