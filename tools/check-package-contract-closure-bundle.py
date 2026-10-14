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
OBSERVER_REPOSITORY = "roccho-dev/governance"
OBSERVER_PATH = "tools/check-package-contract-closure-bundle.py"
OPS_CEILING = "OPS_SELF_DIFF_CONSUMED_NOT_ORGANIZATION_ADMISSION"
OBLIGATION = "ops.final-ci-migration-consumer.v1"
ROLE = "final-ci-receipt"
EXPECTED_NEGATIVE = {
    "contract-drift": "OPEN",
    "missing-observation": "OPEN",
    "wrong-candidate": "OPEN",
    "missing-admission": "UNKNOWN",
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


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
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def check_token(value: str) -> str:
    token = value.replace(" / ", "/").replace(" ", "")
    need(token != "" and " " not in token, "check-token")
    return token


def semantic_contract(repository: str, role: str, branch: str, check: str, assertion: str, binding: str) -> dict[str, Any]:
    body = {
        "capability": "final-ci-migration-consumer",
        "consumer": repository,
        "stage": role,
        "target": {"provider": "github", "resource": check_token(check), "account": branch},
        "slot": assertion,
        "binding": binding,
        "profile": [{"role": ROLE, "operation": "check", "readback": True, "grade": "real"}],
    }
    return {"obligation_digest": digest(body), **body}


def verify_source_binding(
    bindings: dict[str, Any],
    key: str,
    repository: str,
    revision: str,
    source_path: str,
    native: Path,
    bundle: Path,
) -> dict[str, Any]:
    row = bindings.get(key)
    need(isinstance(row, dict), "source-binding:" + key)
    source = row.get("source")
    need(isinstance(source, dict), "source-descriptor:" + key)
    need(source.get("repository") == repository, "source-repository:" + key)
    need(source.get("revision") == revision, "source-revision:" + key)
    need(source.get("path") == source_path, "source-path:" + key)
    carried = bundle / str(row.get("bundlePath", ""))
    need(native.is_file() and not native.is_symlink(), "source-native:" + key)
    need(carried.is_file() and not carried.is_symlink(), "source-carried:" + key)
    need(carried.read_bytes() == native.read_bytes(), "source-bytes:" + key)
    need(source.get("digest") == sha256_file(native), "source-digest:" + key)
    return source


def verify_bundle(
    bundle: Path,
    ops_source: Path,
    ops_candidate: str,
    accepted_governance: Path,
    governance_candidate: str | None = None,
) -> dict[str, Any]:
    bundle = bundle.resolve()
    ops_source = ops_source.resolve()
    accepted_governance = accepted_governance.resolve()
    governance_candidate = governance_candidate or read_object(bundle / "bound-verification.json", "bound").get("observerRevision")
    need(HEX40.fullmatch(ops_candidate) is not None, "ops-candidate")
    need(isinstance(governance_candidate, str) and HEX40.fullmatch(governance_candidate) is not None, "governance-candidate")
    need(bundle.is_dir(), "bundle")

    verifier = ops_source / OPS_VERIFIER_PATH
    need(verifier.is_file() and not verifier.is_symlink(), "verifier-source")
    bindings = read_object(bundle / "source-bindings.json", "source-bindings")
    verifier_source = verify_source_binding(
        bindings, "binder", "roccho-org/ops", ops_candidate, OPS_VERIFIER_PATH,
        verifier, bundle,
    )

    observer_native = Path(__file__).resolve()
    observer_source = verify_source_binding(
        bindings, "observer", OBSERVER_REPOSITORY, governance_candidate, OBSERVER_PATH,
        observer_native, bundle,
    )

    process = run([sys.executable, str(verifier), "verify", "--bundle", str(bundle)], ops_source)
    need(process.returncode == 0 and process.stdout.strip() != "", "verifier-execution")
    verified = json.loads(process.stdout)
    need(verified.get("status") == "PASS", "verifier-status")
    need(verified.get("authority") is False and verified.get("adoption") is False, "verifier-authority")
    need(verified.get("releasePublished") is False and verified.get("remaining") == 0, "verifier-boundary")
    need(verified.get("claimCeiling") == OPS_CEILING, "verifier-ceiling")
    need(verified.get("opsCandidate") == ops_candidate, "verifier-candidate")
    need(verified.get("governanceRevision") == GOVERNANCE_REVISION, "verifier-governance")
    need(verified.get("observerRevision") == governance_candidate, "verifier-observer-revision")
    need(verified.get("sourceBytesVerified") == 8, "verifier-source-count")
    need(verified.get("receiptReplayed") is True and verified.get("comparatorReplayed") is True, "verifier-replay")
    need(verified.get("evidenceBound") is True, "verifier-evidence-bound")

    accepted_files = {
        "acceptedDecision": "governance/accepted-final-ci-decision.v1.json",
        "acceptedRollout": "governance/selected-final-ci-rollout.v1.json",
    }
    accepted_sources: dict[str, dict[str, Any]] = {}
    for key, relative in accepted_files.items():
        accepted_sources[key] = verify_source_binding(
            bindings, key, "roccho-dev/governance", GOVERNANCE_REVISION, relative,
            accepted_governance / relative, bundle,
        )

    scope_path = bundle / "run-scope.json"
    evidence_path = bundle / "phase4-evidence.json"
    scope = read_object(scope_path, "scope")
    evidence = read_object(evidence_path, "evidence")
    need(scope.get("selectedObligations") == [OBLIGATION], "scope-obligation")
    need(scope.get("opsCandidate") == ops_candidate, "scope-candidate")
    need(scope.get("governanceRevision") == GOVERNANCE_REVISION, "scope-governance")
    need(scope.get("authority") is False, "scope-authority")

    decision = read_object(accepted_governance / accepted_files["acceptedDecision"], "accepted-decision")
    rollout = read_object(accepted_governance / accepted_files["acceptedRollout"], "accepted-rollout")
    selected = [row for row in rollout.get("repositories", []) if isinstance(row, dict) and row.get("assertionId") == OBLIGATION]
    need(len(selected) == 1, "accepted-selection")
    accepted = selected[0]
    need(decision.get("stableRequiredCheck") == "gov-final-scope-purpose-join / gate", "accepted-final-check")
    need(accepted.get("repository") == "roccho-dev/ops", "accepted-repository")
    need(accepted.get("acceptedBundleDigest") == "sha256:" + str(decision.get("contractCanonicalDigest")), "accepted-binding")
    required_contract = semantic_contract(
        accepted["repository"], accepted["role"], accepted["branch"], decision["stableRequiredCheck"],
        accepted["assertionId"], accepted["acceptedBundleDigest"],
    )
    need(scope.get("acceptedRequirementDigest") == required_contract["obligation_digest"], "scope-accepted-reconstruction")

    packet = read_object(bundle / "contract-diff-input.json", "contract-diff-input")
    need(packet.get("required", {}).get("rows") == [{"id": OBLIGATION, "contract": required_contract}], "packet-required-reconstruction")
    need(packet.get("required", {}).get("source") == accepted_sources["acceptedRollout"], "packet-required-source")
    need(packet.get("observations", {}).get("source") == observer_source, "packet-observer-source")
    receipt_rows = packet.get("receipts", {}).get("rows")
    need(isinstance(receipt_rows, list) and len(receipt_rows) == 1 and isinstance(receipt_rows[0], dict), "packet-receipt-row")

    expected_evidence = {
        "kind": "ops.contract632.phase4Evidence.v1",
        "status": "PASS",
        "authority": False,
        "adoption": False,
        "releasePublished": False,
        "claimCeiling": OPS_CEILING,
        "scope": scope,
        "acceptedRequirement": {
            "source": accepted_sources["acceptedRollout"],
            "decisionSource": accepted_sources["acceptedDecision"],
            "obligationId": OBLIGATION,
            "contract": required_contract,
        },
        "provider": {
            "source": bindings["providerClaim"]["source"],
            "claimDigest": sha256_file(bundle / bindings["providerClaim"]["bundlePath"]),
        },
        "observation": {"source": observer_source, "candidate": ops_candidate},
        "receipt": {
            "source": bindings["receiptProducer"]["source"],
            "actualReceiptDigest": sha256_file(bundle / "ops-final-ci-consumer-receipt.json"),
            "normalizedReceiptDigest": digest(receipt_rows[0]),
        },
        "comparator": {
            "source": bindings["comparatorCore"]["source"],
            "positive": read_object(bundle / "contract-diff-positive.json", "positive"),
            "negative": {
                name: read_object(bundle / f"contract-diff-negative-{name}.json", "negative:" + name)
                for name in EXPECTED_NEGATIVE
            },
        },
        "remaining": 0,
    }
    need(evidence == expected_evidence, "evidence-reconstruction")
    positive = expected_evidence["comparator"]["positive"]
    negative = expected_evidence["comparator"]["negative"]
    need(positive.get("status") == "CLOSED" and positive.get("findings") == [], "positive")
    need({key: value.get("status") for key, value in negative.items()} == EXPECTED_NEGATIVE, "negative")
    need(verified.get("scopeDigest") == sha256_file(scope_path), "scope-digest")
    need(verified.get("evidenceDigest") == sha256_file(evidence_path), "evidence-digest")

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
        "governanceCandidate": governance_candidate,
        "acceptedRequirementDigest": required_contract["obligation_digest"],
        "contractDiffStatus": "CLOSED",
        "negativeStatus": EXPECTED_NEGATIVE,
        "scopeDigest": sha256_file(scope_path),
        "evidenceDigest": sha256_file(evidence_path),
        "remaining": 0,
        "evidenceBound": True,
        "observerMeaningVerified": True,
        "evidenceReconstructed": True,
        "sourceBytesVerified": verified["sourceBytesVerified"],
        "receiptReplayed": True,
        "comparatorReplayed": True,
        "opsVerifierPath": OPS_VERIFIER_PATH,
        "opsVerifierDigest": verifier_source["digest"],
        "observerPath": OBSERVER_PATH,
        "observerDigest": observer_source["digest"],
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
    parser.add_argument("--governance-candidate")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = verify_bundle(args.bundle, args.ops_source, args.ops_candidate, args.accepted_governance, args.governance_candidate)
    text = canonical(report) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
