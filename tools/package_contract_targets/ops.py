#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

TARGET_ID = "ops"
LOGICAL_REPOSITORY = "roccho-dev/ops"
PROVIDER_REPOSITORY = "roccho-org/ops"
CLAIM_CEILING = "OPS_SELF_DIFF_CONSUMED_NOT_ORGANIZATION_ADMISSION"
OBLIGATION_ID = "ops.final-ci-migration-consumer.v1"
ROLE = "final-ci-receipt"
LOWER_VERIFIER_PATH = "tools/contract-632-phase4-bind.py"
SCOPE_CANDIDATE_FIELD = "opsCandidate"
LOWER_FIELDS = {
    "candidate": "opsCandidate",
    "acceptedRevision": "governanceRevision",
    "observerRevision": "observerRevision",
}
SOURCE_PATHS = {
    "providerClaim": "governance/final-ci-claim.v1.json",
    "receiptProducer": "tools/check-final-ci-consumer.py",
    "comparatorCli": "packages/contract-diff/bin/contract-diff.py",
    "comparatorCore": "packages/contract-diff/core.py",
    "binder": LOWER_VERIFIER_PATH,
}
ACCEPTED_FILES = {
    "acceptedDecision": "governance/accepted-final-ci-decision.v1.json",
    "acceptedRollout": "governance/selected-final-ci-rollout.v1.json",
}
EXPECTED_NEGATIVE = {
    "contract-drift": "OPEN",
    "missing-observation": "OPEN",
    "wrong-candidate": "OPEN",
    "missing-admission": "UNKNOWN",
}
STATUS_EXIT = {"CLOSED": 0, "OPEN": 2, "INVALID": 3, "UNKNOWN": 4}


def describe() -> dict[str, Any]:
    return {
        "targetId": TARGET_ID,
        "logicalRepository": LOGICAL_REPOSITORY,
        "providerRepository": PROVIDER_REPOSITORY,
        "claimCeiling": CLAIM_CEILING,
        "obligationId": OBLIGATION_ID,
        "lowerVerifierPath": LOWER_VERIFIER_PATH,
        "sourcePaths": SOURCE_PATHS,
        "acceptedFiles": ACCEPTED_FILES,
        "expectedNegative": EXPECTED_NEGATIVE,
        "statusExit": STATUS_EXIT,
    }


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def produce(context: dict[str, Any]) -> dict[str, Any]:
    """Build target-owned materials. This does not return a final pass verdict."""
    bundle = Path(context["bundle"]).resolve()
    target_source = Path(context["targetSourceRoot"]).resolve()
    accepted_source = Path(context["acceptedRequirementRoot"]).resolve()
    policy_source = Path(context["governancePolicyRoot"]).resolve()
    observer_root = Path(context["observerRoot"]).resolve()
    target_candidate = str(context["targetCandidate"])
    accepted_revision = str(context["acceptedRequirementRevision"])
    observer_revision = str(context["governanceCandidate"])
    adapter_path = str(context["adapterPath"])

    bundle.parent.mkdir(parents=True, exist_ok=True)
    build = _run(
        [
            sys.executable,
            str(target_source / "tools/contract-632-phase4-proof.py"),
            "build",
            "--governance-source",
            str(policy_source),
            "--governance-revision",
            accepted_revision,
            "--ops-source",
            str(target_source),
            "--ops-candidate",
            target_candidate,
            "--observer-root",
            str(observer_root),
            "--observer-repository",
            "roccho-dev/governance",
            "--observer-revision",
            observer_revision,
            "--observer-path",
            adapter_path,
            "--contract-diff",
            str(target_source / "packages/contract-diff/bin/contract-diff.py"),
            "--out",
            str(bundle),
        ],
        target_source,
    )
    if build.returncode != 0:
        raise ValueError("ops-produce:build:" + build.stderr.strip())
    bind = _run(
        [
            sys.executable,
            str(target_source / LOWER_VERIFIER_PATH),
            "bind",
            "--bundle",
            str(bundle),
            "--governance-source",
            str(accepted_source),
            "--governance-revision",
            accepted_revision,
            "--ops-source",
            str(target_source),
            "--ops-candidate",
            target_candidate,
            "--observer-root",
            str(observer_root),
            "--observer-repository",
            "roccho-dev/governance",
            "--observer-revision",
            observer_revision,
            "--observer-path",
            adapter_path,
        ],
        target_source,
    )
    if bind.returncode != 0:
        raise ValueError("ops-produce:bind:" + bind.stderr.strip())
    verify = _run(
        [
            sys.executable,
            str(target_source / LOWER_VERIFIER_PATH),
            "verify",
            "--bundle",
            str(bundle),
        ],
        target_source,
    )
    if verify.returncode != 0 or not verify.stdout.strip():
        raise ValueError("ops-produce:verify:" + verify.stderr.strip())

    producer_root = bundle.parent / (bundle.name + "-producer")
    producer_root.mkdir(parents=True, exist_ok=True)
    (producer_root / "build.json").write_text(build.stdout, encoding="utf-8")
    (producer_root / "bind.json").write_text(bind.stdout, encoding="utf-8")
    (producer_root / "readback.json").write_text(verify.stdout, encoding="utf-8")
    return {
        "kind": "governance.packageContractTargetMaterials.v1",
        "targetId": TARGET_ID,
        "bundle": str(bundle),
        "producerFiles": ["build.json", "bind.json", "readback.json"],
        "authority": False,
    }


def required_contract(
    decision: dict[str, Any],
    rollout: dict[str, Any],
    digest: Callable[[Any], str],
    check_token: Callable[[str], str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = [
        row
        for row in rollout.get("repositories", [])
        if isinstance(row, dict) and row.get("assertionId") == OBLIGATION_ID
    ]
    if len(selected) != 1:
        raise ValueError("ops-adapter:accepted-selection")
    accepted = selected[0]
    if decision.get("stableRequiredCheck") != "gov-final-scope-purpose-join / gate":
        raise ValueError("ops-adapter:accepted-final-check")
    if accepted.get("repository") != LOGICAL_REPOSITORY:
        raise ValueError("ops-adapter:accepted-repository")
    if accepted.get("acceptedBundleDigest") != "sha256:" + str(
        decision.get("contractCanonicalDigest")
    ):
        raise ValueError("ops-adapter:accepted-binding")
    body = {
        "capability": "final-ci-migration-consumer",
        "consumer": accepted["repository"],
        "stage": accepted["role"],
        "target": {
            "provider": "github",
            "resource": check_token(decision["stableRequiredCheck"]),
            "account": accepted["branch"],
        },
        "slot": accepted["assertionId"],
        "binding": accepted["acceptedBundleDigest"],
        "profile": [
            {
                "role": ROLE,
                "operation": "check",
                "readback": True,
                "grade": "real",
            }
        ],
    }
    return accepted, {"obligation_digest": digest(body), **body}


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
    return {
        "kind": "ops.contract632.phase4Evidence.v1",
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
            "contract": required_contract,
        },
        "provider": {
            "source": sources["providerClaim"],
            "claimDigest": sha256_file(
                bundle / bindings["providerClaim"]["bundlePath"]
            ),
        },
        "observation": {
            "source": sources["observer"],
            "candidate": scope[SCOPE_CANDIDATE_FIELD],
        },
        "receipt": {
            "source": sources["receiptProducer"],
            "actualReceiptDigest": sha256_file(
                bundle / "ops-final-ci-consumer-receipt.json"
            ),
            "normalizedReceiptDigest": digest(receipt_rows[0]),
        },
        "comparator": {
            "source": sources["comparatorCore"],
            "positive": read_object(
                bundle / "contract-diff-positive.json", "positive"
            ),
            "negative": {
                name: read_object(
                    bundle / f"contract-diff-negative-{name}.json",
                    "negative:" + name,
                )
                for name in EXPECTED_NEGATIVE
            },
        },
        "remaining": 0,
    }
