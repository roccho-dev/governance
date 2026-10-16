#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIGEST_PREFIX = "sha256:"
STATUS_EXIT = {"CLOSED": 0, "OPEN": 2, "INVALID": 3, "UNKNOWN": 4}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(code: str, detail: Any = None) -> None:
    suffix = "" if detail is None else ":" + canonical(detail)
    raise SystemExit(code + suffix)


def need(ok: bool, code: str, detail: Any = None) -> None:
    if not ok:
        fail(code, detail)


def sha256(path: Path) -> str:
    return DIGEST_PREFIX + hashlib.sha256(path.read_bytes()).hexdigest()


def deep_diff(left: Any, right: Any, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if type(left) is not type(right):
        return {prefix}
    if isinstance(left, dict):
        paths: set[tuple[str, ...]] = set()
        for key in set(left) | set(right):
            if key not in left or key not in right:
                paths.add(prefix + (str(key),))
            else:
                paths |= deep_diff(left[key], right[key], prefix + (str(key),))
        return paths
    if isinstance(left, list):
        if len(left) != len(right):
            return {prefix + ("length",)}
        paths: set[tuple[str, ...]] = set()
        for index, (lvalue, rvalue) in enumerate(zip(left, right)):
            paths |= deep_diff(lvalue, rvalue, prefix + (str(index),))
        return paths
    return set() if left == right else {prefix}


def require_diff(path: str, left: Any, right: Any, allowed: set[tuple[str, ...]]) -> None:
    actual = deep_diff(left, right)
    if actual != allowed:
        fail("unexpected-pointer-delta:" + path, {"actual": sorted(actual), "allowed": sorted(allowed)})


EXPECTED_CHANGED = {
    "sources/observer/source",
    "source-bindings.json",
    "bound-verification.json",
    "contract-diff-input.json",
    "contract-diff-admission.json",
    "contract-diff-positive.json",
    "negative-contract-drift-input.json",
    "negative-contract-drift-admission.json",
    "contract-diff-negative-contract-drift.json",
    "negative-missing-observation-input.json",
    "negative-missing-observation-admission.json",
    "contract-diff-negative-missing-observation.json",
    "negative-wrong-candidate-input.json",
    "negative-wrong-candidate-admission.json",
    "contract-diff-negative-wrong-candidate.json",
    "negative-missing-admission-input.json",
    "phase4-evidence.json",
    "bundle-manifest.json",
}
STABLE = {
    "run-scope.json",
    "negative-missing-admission-admission.json",
    "contract-diff-negative-missing-admission.json",
    "ops-final-ci-consumer-receipt.json",
}
SOURCE_FIELDS = {("revision",), ("path",), ("digest",)}


def normalize(value: Any, manifest: bool = False) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        observer = value.get("repository") == "roccho-dev/governance" and value.get("path") in {
            "tools/check-package-contract-closure-bundle.py",
            "tools/package_contract_targets/ops.py",
        }
        for key, item in value.items():
            if observer and key in {"revision", "path", "digest"}:
                out[key] = "<observer-" + key + ">"
            elif key in {"observerRevision", "observerPath", "observerDigest"}:
                out[key] = "<" + key + ">"
            elif key in {"input_manifest_digest", "inputManifestDigest"}:
                out[key] = "<rebound-manifest>"
            else:
                out[key] = normalize(item, manifest)
        return out
    if isinstance(value, list):
        rows = [normalize(item, manifest) for item in value]
        if manifest:
            for row in rows:
                if isinstance(row, dict) and row.get("path") in EXPECTED_CHANGED:
                    row["sha256"] = "<rebound-file>"
        return rows
    return value


V2_FIELDS = {
    "kind", "status", "authority", "adoption", "releasePublished", "claimCeiling",
    "scopeId", "obligationId", "opsCandidate", "governanceCandidate",
    "acceptedRequirementDigest", "contractDiffStatus", "negativeStatus",
    "scopeDigest", "evidenceDigest", "remaining", "evidenceBound",
    "observerMeaningVerified", "evidenceReconstructed",
    "opsCandidateSourceClosureVerified", "opsCandidateSourcesVerified",
    "sourceBytesVerified", "receiptReplayed", "comparatorReplayed",
    "opsVerifierPath", "opsVerifierDigest", "observerPath", "observerDigest",
    "acceptedGovernanceRevision", "bundleManifestDigest", "memberDigest",
}
V3_FIELDS = {
    "kind", "status", "authority", "adoption", "releasePublished", "claimCeiling",
    "targetId", "logicalRepository", "providerRepository", "scopeId", "obligationId",
    "targetCandidate", "governanceCandidate", "acceptedRequirementDigest",
    "acceptedRequirementRevision", "governancePolicyRevision",
    "contractRuntimeRepository", "contractRuntimeRevision", "contractDiffStatus",
    "contractDiffExit", "negativeStatus", "negativeExit", "scopeDigest", "evidenceDigest",
    "evidenceInputVerified", "evidenceInputMode", "evidenceInputDigest",
    "evidenceInputFilesVerified", "evidenceExecutor", "remaining", "evidenceBound",
    "observerMeaningVerified", "evidenceReconstructed", "targetSourceClosureVerified",
    "targetSourcesVerified", "targetNativeSourcesVerified", "runtimeSourcesVerified",
    "sourceBytesVerified", "receiptReplayed", "comparatorReplayed", "lowerProofMode",
    "lowerVerifierPath", "lowerVerifierDigest", "adapterPath", "adapterDigest",
    "targetBindingPath", "targetBindingDigest", "commonCheckerPath", "commonCheckerDigest",
    "bundleManifestDigest", "memberDigest",
}
DIRECT = {
    "status", "authority", "adoption", "releasePublished", "claimCeiling", "scopeId",
    "obligationId", "acceptedRequirementDigest", "contractDiffStatus", "negativeStatus",
    "remaining", "evidenceBound", "observerMeaningVerified", "evidenceReconstructed",
    "sourceBytesVerified", "receiptReplayed", "comparatorReplayed",
}
RENAMED = {
    "opsCandidate": "targetCandidate",
    "opsCandidateSourceClosureVerified": "targetSourceClosureVerified",
    "opsCandidateSourcesVerified": "targetSourcesVerified",
    "opsVerifierPath": "lowerVerifierPath",
    "opsVerifierDigest": "lowerVerifierDigest",
    "observerPath": "commonCheckerPath",
}
V2_BOUND = {
    "governanceCandidate", "scopeDigest", "evidenceDigest", "observerDigest",
    "bundleManifestDigest", "memberDigest",
}
V3_BOUND = {
    "governanceCandidate", "scopeDigest", "evidenceDigest", "commonCheckerDigest",
    "bundleManifestDigest", "memberDigest",
}
V3_DERIVED = {
    "targetId", "logicalRepository", "providerRepository", "contractRuntimeRepository",
    "contractRuntimeRevision", "contractDiffExit", "negativeExit", "evidenceInputVerified",
    "evidenceInputMode", "evidenceInputDigest", "evidenceInputFilesVerified",
    "evidenceExecutor", "targetNativeSourcesVerified", "runtimeSourcesVerified",
    "lowerProofMode", "adapterPath", "adapterDigest", "targetBindingPath",
    "targetBindingDigest",
}


def valid_hex40(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value)


def valid_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith(DIGEST_PREFIX)
        and all(c in "0123456789abcdef" for c in value[7:])
    )


def member_digest(value: dict[str, Any]) -> str:
    body = {key: item for key, item in value.items() if key != "memberDigest"}
    return DIGEST_PREFIX + hashlib.sha256(canonical(body).encode()).hexdigest()


def validate_classification() -> None:
    v2_groups = [DIRECT, set(RENAMED), {"acceptedGovernanceRevision"}, {"kind"}, V2_BOUND]
    v3_groups = [DIRECT, set(RENAMED.values()), {"acceptedRequirementRevision", "governancePolicyRevision"}, {"kind"}, V3_BOUND, V3_DERIVED]
    need(set().union(*v2_groups) == V2_FIELDS, "v2-field-classification")
    need(sum(len(group) for group in v2_groups) == len(V2_FIELDS), "v2-field-classification-overlap")
    need(set().union(*v3_groups) == V3_FIELDS, "v3-field-classification")
    need(sum(len(group) for group in v3_groups) == len(V3_FIELDS), "v3-field-classification-overlap")


def validate_member_mapping(v2: dict[str, Any], v3: dict[str, Any], b0_root: Path, b1: Path) -> dict[str, Any]:
    need(set(v2) == V2_FIELDS, "v2-field-universe", {"missing": sorted(V2_FIELDS - set(v2)), "extra": sorted(set(v2) - V2_FIELDS)})
    need(set(v3) == V3_FIELDS, "v3-field-universe", {"missing": sorted(V3_FIELDS - set(v3)), "extra": sorted(set(v3) - V3_FIELDS)})
    validate_classification()
    for key in sorted(DIRECT):
        need(v2[key] == v3[key], "member-direct-drift:" + key)
    for old, new in RENAMED.items():
        need(v2[old] == v3[new], "member-mapped-drift:" + old + "->" + new)
    accepted = v2["acceptedGovernanceRevision"]
    need(v3["acceptedRequirementRevision"] == accepted, "member-accepted-revision")
    need(v3["governancePolicyRevision"] == accepted, "member-policy-revision")
    need(v2["kind"] == "governance.packageContractClosureMember.v2", "v2-kind")
    need(v3["kind"] == "governance.packageContractClosureMember.v3", "v3-kind")

    binding_path = ROOT / "tools/package_contract_targets/ops.target.json"
    binding = read(binding_path)
    roots = binding["sourceRoots"]
    target_count = sum(root == "target" for root in roots.values())
    runtime_count = sum(root == "runtime" for root in roots.values())
    accepted_count = len(binding["acceptedRequirementSource"]["allowedPaths"])
    expected = {
        "targetId": binding["targetId"],
        "logicalRepository": binding["logicalRepository"],
        "providerRepository": binding["providerRepository"],
        "contractRuntimeRepository": binding["contractRuntimeSource"]["repository"],
        "contractRuntimeRevision": binding["contractRuntimeSource"]["revision"],
        "contractDiffExit": STATUS_EXIT[v3["contractDiffStatus"]],
        "negativeExit": {name: STATUS_EXIT[status] for name, status in v3["negativeStatus"].items()},
        "evidenceInputVerified": True,
        "evidenceInputMode": binding["evidenceExecutor"]["kind"],
        "evidenceInputFilesVerified": 1,
        "evidenceExecutor": binding["evidenceExecutor"],
        "targetNativeSourcesVerified": target_count,
        "runtimeSourcesVerified": runtime_count,
        "lowerProofMode": "target-verifier+common-reconstruction",
        "adapterPath": binding["adapterPath"],
        "targetBindingPath": "tools/package_contract_targets/ops.target.json",
    }
    for key, value in expected.items():
        need(v3[key] == value, "member-derived-drift:" + key)
    need(binding["lowerVerifier"]["mode"] == "required", "member-lower-verifier-mode")
    need(v3["targetSourcesVerified"] == target_count + runtime_count, "member-source-partition")
    need(v3["sourceBytesVerified"] == len(roots) + accepted_count + 1, "member-source-total")

    b0 = b0_root / "ops-bundle"
    need(valid_hex40(v2["governanceCandidate"]), "v2-governance-candidate")
    need(valid_hex40(v3["governanceCandidate"]), "v3-governance-candidate")
    need(v2["governanceCandidate"] != v3["governanceCandidate"], "governance-candidate-not-rebound")
    need(v2["scopeDigest"] == sha256(b0 / "run-scope.json"), "v2-scope-digest")
    need(v3["scopeDigest"] == sha256(b1 / "run-scope.json"), "v3-scope-digest")
    need(v2["scopeDigest"] == v3["scopeDigest"], "member-scope-drift")
    need(v2["evidenceDigest"] == sha256(b0 / "phase4-evidence.json"), "v2-evidence-digest")
    need(v3["evidenceDigest"] == sha256(b1 / "phase4-evidence.json"), "v3-evidence-digest")
    need(v2["observerDigest"] == sha256(b0 / "sources/observer/source"), "v2-observer-digest")
    need(v2["bundleManifestDigest"] == sha256(b0 / "bundle-manifest.json"), "v2-bundle-manifest-digest")
    need(v3["bundleManifestDigest"] == sha256(b1 / "bundle-manifest.json"), "v3-bundle-manifest-digest")
    need(v3["adapterDigest"] == sha256(ROOT / v3["adapterPath"]), "v3-adapter-digest")
    need(v3["targetBindingDigest"] == sha256(binding_path), "v3-target-binding-digest")
    need(v3["commonCheckerDigest"] == sha256(ROOT / v3["commonCheckerPath"]), "v3-common-checker-digest")
    need(valid_digest(v3["evidenceInputDigest"]), "v3-evidence-input-digest")
    need(v2["memberDigest"] == member_digest(v2), "v2-member-digest")
    need(v3["memberDigest"] == member_digest(v3), "v3-member-digest")
    return {
        "v2FieldCount": len(V2_FIELDS),
        "v3FieldCount": len(V3_FIELDS),
        "direct": sorted(DIRECT),
        "renamed": RENAMED,
        "split": {"acceptedGovernanceRevision": ["acceptedRequirementRevision", "governancePolicyRevision"]},
        "v2Bound": sorted(V2_BOUND),
        "v3Bound": sorted(V3_BOUND),
        "v3Derived": sorted(V3_DERIVED),
    }


def rejects(v2: dict[str, Any], v3: dict[str, Any], b0: Path, b1: Path, mutate) -> bool:
    candidate = copy.deepcopy(v3)
    mutate(candidate)
    try:
        validate_member_mapping(v2, candidate, b0, b1)
    except SystemExit:
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("b0", "b1", "member", "out"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    b0_root = Path(args.b0)
    b0 = b0_root / "ops-bundle"
    b1 = Path(args.b1)
    paths0 = {x.relative_to(b0).as_posix() for x in b0.rglob("*") if x.is_file()}
    paths1 = {x.relative_to(b1).as_posix() for x in b1.rglob("*") if x.is_file()}
    if paths0 != paths1:
        fail("bundle-path-set", {"onlyB0": sorted(paths0 - paths1), "onlyB1": sorted(paths1 - paths0)})
    changed = {x for x in paths0 if (b0 / x).read_bytes() != (b1 / x).read_bytes()}
    if changed != EXPECTED_CHANGED:
        fail("unexpected-delta-files", {"actual": sorted(changed), "expected": sorted(EXPECTED_CHANGED)})
    for path in STABLE:
        if (b0 / path).read_bytes() != (b1 / path).read_bytes():
            fail("stable-byte-drift:" + path)

    input_paths = [
        "contract-diff-input.json",
        "negative-contract-drift-input.json",
        "negative-missing-observation-input.json",
        "negative-wrong-candidate-input.json",
        "negative-missing-admission-input.json",
    ]
    for path in input_paths:
        allowed = {("observations", "source") + item for item in SOURCE_FIELDS}
        require_diff(path, read(b0 / path), read(b1 / path), allowed)

    admission_paths = [
        "contract-diff-admission.json",
        "negative-contract-drift-admission.json",
        "negative-missing-observation-admission.json",
        "negative-wrong-candidate-admission.json",
    ]
    for path in admission_paths:
        left, right = read(b0 / path), read(b1 / path)
        allowed = {("inventory", "observations", "source") + item for item in SOURCE_FIELDS}
        require_diff(path, left, right, allowed)
        if left["inventory"]["observations"]["count"] != right["inventory"]["observations"]["count"]:
            fail("observation-count-drift:" + path)
        if left["inventory"]["observations"]["rows_digest"] != right["inventory"]["observations"]["rows_digest"]:
            fail("observation-rows-digest-drift:" + path)

    if read(b0 / "negative-missing-admission-admission.json") != {} or read(b1 / "negative-missing-admission-admission.json") != {}:
        fail("missing-admission-not-empty")
    if (b0 / "contract-diff-negative-missing-admission.json").read_bytes() != (b1 / "contract-diff-negative-missing-admission.json").read_bytes():
        fail("missing-admission-result-drift")

    result_paths = [
        "contract-diff-positive.json",
        "contract-diff-negative-contract-drift.json",
        "contract-diff-negative-missing-observation.json",
        "contract-diff-negative-wrong-candidate.json",
    ]
    allowed_result = {
        ("sources", "observations", "revision"),
        ("sources", "observations", "path"),
        ("sources", "observations", "digest"),
        ("input_manifest_digest",),
    }
    for path in result_paths:
        require_diff(path, read(b0 / path), read(b1 / path), allowed_result)

    manifest0, manifest1 = read(b0 / "bundle-manifest.json"), read(b1 / "bundle-manifest.json")
    rows0 = {row["path"]: row["sha256"] for row in manifest0}
    rows1 = {row["path"]: row["sha256"] for row in manifest1}
    if set(rows0) != set(rows1):
        fail("manifest-path-set")
    manifest_changed = {path for path in rows0 if rows0[path] != rows1[path]}
    if manifest_changed != EXPECTED_CHANGED - {"bundle-manifest.json"}:
        fail("manifest-delta", {"actual": sorted(manifest_changed)})
    for path in sorted(changed - {"sources/observer/source"}):
        if normalize(read(b0 / path), path == "bundle-manifest.json") != normalize(read(b1 / path), path == "bundle-manifest.json"):
            fail("unexpected-semantic-delta:" + path)

    v2 = read(b0_root / "package-contract-member.json")
    v3 = read(Path(args.member))
    mapping = validate_member_mapping(v2, v3, b0_root, b1)
    negatives = {
        "memberExtraFieldRejected": rejects(v2, v3, b0_root, b1, lambda value: value.__setitem__("unexpected", True)),
        "memberMissingFieldRejected": rejects(v2, v3, b0_root, b1, lambda value: value.pop("targetId")),
        "memberMappedFieldDriftRejected": rejects(v2, v3, b0_root, b1, lambda value: value.__setitem__("targetCandidate", "0" * 40)),
        "memberBoundFieldDriftRejected": rejects(v2, v3, b0_root, b1, lambda value: value.__setitem__("evidenceDigest", DIGEST_PREFIX + "0" * 64)),
    }
    need(all(negatives.values()), "member-negative-suite")

    report = {
        "kind": "governance.contract632.b0B1PrimePortEquivalence.v2",
        "status": "pass",
        "authority": False,
        "semanticInvariant": True,
        "stableByteInvariant": True,
        "expectedDeltaClosed": True,
        "negativeDeltaMapClosed": True,
        "manifestDeltaClosed": True,
        "runtimeSeparated": True,
        "lowerProofPreservedForOps": True,
        "fieldUniverseClosed": True,
        "fieldClassificationClosed": True,
        "memberMapping": mapping,
        "changedFiles": sorted(changed),
        **negatives,
    }
    Path(args.out).write_text(canonical(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
