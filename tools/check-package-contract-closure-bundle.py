#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HEX40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
GOVERNANCE_REVISION = "5b26984eb59e4c03f9d0fe34891fea5e4a436a16"
OPS_VERIFIER_PATH = "tools/contract-632-phase4-bind.py"
OPS_CEILING = "OPS_SELF_DIFF_CONSUMED_NOT_ORGANIZATION_ADMISSION"
OBLIGATION = "ops.final-ci-migration-consumer.v1"
EXPECTED_NEGATIVE = {
    "contract-drift": "OPEN",
    "missing-observation": "OPEN",
    "wrong-candidate": "OPEN",
    "missing-admission": "UNKNOWN",
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(label + "-not-object")
    return value


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("package-contract-bundle:" + code)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def verify_bundle(
    bundle: Path,
    ops_source: Path,
    ops_candidate: str,
    accepted_governance: Path,
) -> dict[str, Any]:
    bundle = bundle.resolve()
    ops_source = ops_source.resolve()
    accepted_governance = accepted_governance.resolve()
    need(HEX40.fullmatch(ops_candidate) is not None, "ops-candidate")
    need(bundle.is_dir(), "bundle")

    verifier = ops_source / OPS_VERIFIER_PATH
    need(verifier.is_file() and not verifier.is_symlink(), "verifier-source")
    bindings = read_object(bundle / "source-bindings.json", "source-bindings")
    verifier_binding = bindings.get("binder")
    need(isinstance(verifier_binding, dict), "verifier-binding")
    verifier_source = verifier_binding.get("source")
    need(isinstance(verifier_source, dict), "verifier-descriptor")
    need(verifier_source.get("repository") == "roccho-org/ops", "verifier-repository")
    need(verifier_source.get("revision") == ops_candidate, "verifier-revision")
    need(verifier_source.get("path") == OPS_VERIFIER_PATH, "verifier-path")
    need(verifier_source.get("digest") == sha256_file(verifier), "verifier-native-digest")
    verifier_copy = bundle / str(verifier_binding.get("bundlePath", ""))
    need(verifier_copy.is_file(), "verifier-copy")
    need(verifier_copy.read_bytes() == verifier.read_bytes(), "verifier-copy-bytes")

    process = run([sys.executable, str(verifier), "verify", "--bundle", str(bundle)], ops_source)
    need(process.returncode == 0 and process.stdout.strip() != "", "verifier-execution")
    verified = json.loads(process.stdout)
    need(verified.get("status") == "PASS", "verifier-status")
    need(verified.get("authority") is False and verified.get("adoption") is False, "verifier-authority")
    need(verified.get("releasePublished") is False and verified.get("remaining") == 0, "verifier-boundary")
    need(verified.get("claimCeiling") == OPS_CEILING, "verifier-ceiling")
    need(verified.get("opsCandidate") == ops_candidate, "verifier-candidate")
    need(verified.get("governanceRevision") == GOVERNANCE_REVISION, "verifier-governance")
    need(verified.get("sourceBytesVerified") == 8, "verifier-source-count")
    need(verified.get("receiptReplayed") is True and verified.get("comparatorReplayed") is True, "verifier-replay")
    need(verified.get("evidenceBound") is True, "verifier-evidence-bound")

    accepted_files = {
        "acceptedDecision": "governance/accepted-final-ci-decision.v1.json",
        "acceptedRollout": "governance/selected-final-ci-rollout.v1.json",
    }
    for key, relative in accepted_files.items():
        binding = bindings.get(key)
        need(isinstance(binding, dict), "accepted-binding:" + key)
        source = binding.get("source")
        need(isinstance(source, dict), "accepted-source:" + key)
        need(source.get("repository") == "roccho-dev/governance", "accepted-repository:" + key)
        need(source.get("revision") == GOVERNANCE_REVISION, "accepted-revision:" + key)
        need(source.get("path") == relative, "accepted-path:" + key)
        native = accepted_governance / relative
        carried = bundle / str(binding.get("bundlePath", ""))
        need(native.is_file() and carried.is_file(), "accepted-file:" + key)
        need(native.read_bytes() == carried.read_bytes(), "accepted-bytes:" + key)
        need(source.get("digest") == sha256_file(native), "accepted-digest:" + key)

    scope_path = bundle / "run-scope.json"
    evidence_path = bundle / "phase4-evidence.json"
    scope = read_object(scope_path, "scope")
    evidence = read_object(evidence_path, "evidence")
    need(scope.get("selectedObligations") == [OBLIGATION], "scope-obligation")
    need(scope.get("opsCandidate") == ops_candidate, "scope-candidate")
    need(scope.get("governanceRevision") == GOVERNANCE_REVISION, "scope-governance")
    need(scope.get("authority") is False, "scope-authority")
    need(evidence.get("scope") == scope, "scope-evidence-binding")
    need(evidence.get("status") == "PASS" and evidence.get("remaining") == 0, "evidence-status")
    need(evidence.get("authority") is False and evidence.get("adoption") is False, "evidence-authority")
    need(evidence.get("releasePublished") is False and evidence.get("claimCeiling") == OPS_CEILING, "evidence-boundary")
    need(verified.get("scopeDigest") == sha256_file(scope_path), "scope-digest")
    need(verified.get("evidenceDigest") == sha256_file(evidence_path), "evidence-digest")

    accepted = evidence.get("acceptedRequirement") or {}
    comparator = evidence.get("comparator") or {}
    positive = comparator.get("positive") or {}
    negative = comparator.get("negative") or {}
    need(accepted.get("obligationId") == OBLIGATION, "accepted-obligation")
    need((accepted.get("contract") or {}).get("obligation_digest") == scope.get("acceptedRequirementDigest"), "accepted-digest")
    need(positive.get("status") == "CLOSED" and positive.get("findings") == [], "positive")
    need({key: value.get("status") for key, value in negative.items() if isinstance(value, dict)} == EXPECTED_NEGATIVE, "negative")

    member = {
        "kind": "governance.packageContractClosureMember.v2",
        "status": "pass",
        "authority": False,
        "adoption": False,
        "releasePublished": False,
        "claimCeiling": OPS_CEILING,
        "scopeId": scope.get("scopeId"),
        "obligationId": OBLIGATION,
        "opsCandidate": ops_candidate,
        "acceptedRequirementDigest": scope.get("acceptedRequirementDigest"),
        "contractDiffStatus": "CLOSED",
        "negativeStatus": EXPECTED_NEGATIVE,
        "scopeDigest": sha256_file(scope_path),
        "evidenceDigest": sha256_file(evidence_path),
        "remaining": 0,
        "evidenceBound": True,
        "sourceBytesVerified": verified["sourceBytesVerified"],
        "receiptReplayed": True,
        "comparatorReplayed": True,
        "opsVerifierPath": OPS_VERIFIER_PATH,
        "opsVerifierDigest": sha256_file(verifier),
        "acceptedGovernanceRevision": GOVERNANCE_REVISION,
        "bundleManifestDigest": sha256_file(bundle / "bundle-manifest.json"),
    }
    member["memberDigest"] = sha256_bytes(canonical(member).encode())
    return member


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("check", nargs="?")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--ops-source", type=Path, required=True)
    parser.add_argument("--ops-candidate", required=True)
    parser.add_argument("--accepted-governance", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = verify_bundle(args.bundle, args.ops_source, args.ops_candidate, args.accepted_governance)
    text = canonical(report) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
