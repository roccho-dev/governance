#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(code: str, detail: Any = None) -> None:
    suffix = "" if detail is None else ":" + canonical(detail)
    raise SystemExit(code + suffix)


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


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("b0", "b1", "member", "out"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    b0 = Path(args.b0) / "ops-bundle"
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
        left, right = read(b0 / path), read(b1 / path)
        allowed = {("observations", "source") + item for item in SOURCE_FIELDS}
        require_diff(path, left, right, allowed)

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

    v2 = read(Path(args.b0) / "package-contract-member.json")
    v3 = read(Path(args.member))
    keys = (
        "status",
        "authority",
        "adoption",
        "releasePublished",
        "claimCeiling",
        "scopeId",
        "obligationId",
        "acceptedRequirementDigest",
        "contractDiffStatus",
        "negativeStatus",
        "remaining",
        "evidenceBound",
        "observerMeaningVerified",
        "evidenceReconstructed",
        "sourceBytesVerified",
        "receiptReplayed",
        "comparatorReplayed",
    )
    for key in keys:
        if v2[key] != v3[key]:
            fail("semantic-member-drift:" + key)
    if (
        v2["opsCandidate"] != v3["targetCandidate"]
        or v2["opsCandidateSourcesVerified"] != v3["targetSourcesVerified"]
        or v2["acceptedGovernanceRevision"] != v3["acceptedRequirementRevision"]
    ):
        fail("semantic-member-mapping")
    if (
        v3.get("contractRuntimeRepository") != "roccho-org/ops"
        or v3.get("contractRuntimeRevision") != "5eb98c82417b399978c1e38aebab5e3fb39752d4"
        or v3.get("runtimeSourcesVerified") != 2
        or v3.get("lowerProofMode") != "target-verifier+common-reconstruction"
        or v3.get("evidenceInputVerified") is not True
    ):
        fail("corrected-port-member")

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
        "changedFiles": sorted(changed),
    }
    Path(args.out).write_text(canonical(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
