#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gov_release.identity import IDENTITY_PATH, load_identity  # noqa: E402

HEX40 = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
PACKAGE_SCOPE_KIND = "ops.contract632.phase4RunScope.v1"
PACKAGE_EVIDENCE_KIND = "ops.contract632.phase4Evidence.v1"
PACKAGE_MEMBER_KIND = "governance.packageContractClosureMember.v1"
PACKAGE_CEILING = "OPS_SELF_DIFF_CONSUMED_NOT_ORGANIZATION_ADMISSION"
PACKAGE_OBLIGATION = "ops.final-ci-migration-consumer.v1"
PACKAGE_GOVERNANCE_REVISION = "5b26984eb59e4c03f9d0fe34891fea5e4a436a16"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(label + "-not-object")
    return value


def package_need(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("package-contract:" + code)


def exact_source(value: Any, repository: str, revision: str, path: str, label: str) -> None:
    package_need(isinstance(value, dict), label + "-source")
    package_need(value.get("repository") == repository, label + "-repository")
    package_need(value.get("revision") == revision, label + "-revision")
    package_need(value.get("path") == path, label + "-path")
    package_need(isinstance(value.get("digest"), str) and DIGEST.fullmatch(value["digest"]) is not None, label + "-digest")


def package_contract_closure(scope_path: Path, evidence_path: Path, expected_ops_candidate: str) -> dict[str, Any]:
    package_need(HEX40.fullmatch(expected_ops_candidate) is not None, "expected-ops-candidate")
    scope = read_object(scope_path, "package-scope")
    evidence = read_object(evidence_path, "package-evidence")

    package_need(scope.get("kind") == PACKAGE_SCOPE_KIND, "scope-kind")
    package_need(scope.get("authority") is False, "scope-authority")
    package_need(scope.get("scopeId") == "contract-632-phase4-ops-self", "scope-id")
    package_need(scope.get("selectedObligations") == [PACKAGE_OBLIGATION], "scope-obligation")
    package_need(scope.get("opsCandidate") == expected_ops_candidate, "scope-candidate")
    package_need(scope.get("governanceRevision") == PACKAGE_GOVERNANCE_REVISION, "scope-governance")
    package_need(isinstance(scope.get("acceptedRequirementDigest"), str) and DIGEST.fullmatch(scope["acceptedRequirementDigest"]) is not None, "scope-requirement-digest")
    package_need(scope.get("requiredEvidenceTypes") == ["final-ci-receipt"], "scope-evidence-types")

    package_need(evidence.get("kind") == PACKAGE_EVIDENCE_KIND, "evidence-kind")
    package_need(evidence.get("status") == "PASS", "evidence-status")
    package_need(evidence.get("authority") is False, "evidence-authority")
    package_need(evidence.get("adoption") is False, "evidence-adoption")
    package_need(evidence.get("releasePublished") is False, "evidence-release")
    package_need(evidence.get("claimCeiling") == PACKAGE_CEILING, "evidence-ceiling")
    package_need(evidence.get("remaining") == 0, "evidence-remaining")
    package_need(evidence.get("scope") == scope, "scope-evidence-binding")

    accepted = evidence.get("acceptedRequirement")
    package_need(isinstance(accepted, dict), "accepted-requirement")
    package_need(accepted.get("obligationId") == PACKAGE_OBLIGATION, "accepted-obligation")
    exact_source(
        accepted.get("source"), "roccho-dev/governance", PACKAGE_GOVERNANCE_REVISION,
        "governance/selected-final-ci-rollout.v1.json", "accepted-rollout",
    )
    exact_source(
        accepted.get("decisionSource"), "roccho-dev/governance", PACKAGE_GOVERNANCE_REVISION,
        "governance/accepted-final-ci-decision.v1.json", "accepted-decision",
    )
    contract = accepted.get("contract")
    package_need(isinstance(contract, dict), "accepted-contract")
    package_need(contract.get("obligation_digest") == scope["acceptedRequirementDigest"], "accepted-contract-digest")
    package_need(contract.get("slot") == PACKAGE_OBLIGATION, "accepted-contract-slot")

    provider = evidence.get("provider")
    package_need(isinstance(provider, dict), "provider")
    exact_source(provider.get("source"), "roccho-org/ops", expected_ops_candidate, "governance/final-ci-claim.v1.json", "provider")
    package_need(provider.get("claimDigest") == provider["source"]["digest"], "provider-digest")

    observation = evidence.get("observation")
    package_need(isinstance(observation, dict), "observation")
    package_need(observation.get("candidate") == expected_ops_candidate, "observation-candidate")
    package_need(isinstance(observation.get("source"), dict), "observation-source")
    package_need(observation["source"].get("revision") == expected_ops_candidate, "observation-revision")
    package_need(isinstance(observation["source"].get("digest"), str) and DIGEST.fullmatch(observation["source"]["digest"]) is not None, "observation-digest")

    receipt = evidence.get("receipt")
    package_need(isinstance(receipt, dict), "receipt")
    exact_source(receipt.get("source"), "roccho-org/ops", expected_ops_candidate, "tools/check-final-ci-consumer.py", "receipt")
    package_need(isinstance(receipt.get("actualReceiptDigest"), str) and DIGEST.fullmatch(receipt["actualReceiptDigest"]) is not None, "receipt-actual-digest")
    package_need(isinstance(receipt.get("normalizedReceiptDigest"), str) and DIGEST.fullmatch(receipt["normalizedReceiptDigest"]) is not None, "receipt-normalized-digest")

    comparator = evidence.get("comparator")
    package_need(isinstance(comparator, dict), "comparator")
    exact_source(comparator.get("source"), "roccho-org/ops", expected_ops_candidate, "packages/contract-diff/core.py", "comparator")
    positive = comparator.get("positive")
    negative = comparator.get("negative")
    package_need(isinstance(positive, dict) and positive.get("status") == "CLOSED" and positive.get("findings") == [], "positive")
    expected_negative = {
        "contract-drift": "OPEN",
        "missing-observation": "OPEN",
        "wrong-candidate": "OPEN",
        "missing-admission": "UNKNOWN",
    }
    package_need(isinstance(negative, dict), "negative")
    package_need({key: value.get("status") for key, value in negative.items() if isinstance(value, dict)} == expected_negative, "negative-status")

    return {
        "kind": PACKAGE_MEMBER_KIND,
        "status": "pass",
        "authority": False,
        "adoption": False,
        "releasePublished": False,
        "claimCeiling": PACKAGE_CEILING,
        "scopeId": scope["scopeId"],
        "obligationId": PACKAGE_OBLIGATION,
        "opsCandidate": expected_ops_candidate,
        "acceptedRequirementDigest": scope["acceptedRequirementDigest"],
        "contractDiffStatus": "CLOSED",
        "negativeStatus": expected_negative,
        "scopeDigest": sha256_file(scope_path),
        "evidenceDigest": sha256_file(evidence_path),
        "remaining": 0,
    }


def run_component(name: str, args: list[str]) -> dict[str, Any]:
    process = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {
        "name": name,
        "status": "pass" if process.returncode == 0 else "fail",
        "exitCode": process.returncode,
        "output": process.stdout.strip().splitlines()[-5:],
    }


def regression_components() -> list[dict[str, Any]]:
    return [
        run_component("package-closure-strict", [sys.executable, "tools/check-package-closure-strict.py", "selftest", "--json"]),
        run_component("required-repo-org-join", [sys.executable, "tools/check-package-required-repo-org-join.py", "selftest"]),
        run_component("provider-ci-yaml", [sys.executable, "tools/check-provider-ci-yaml.py", "selftest"]),
        run_component("merge-write-boundary-final-gate", [sys.executable, "tools/check-merge-write-boundary-final-gate.py", "selftest", "--json"]),
        run_component("fspj-real-join", [sys.executable, "tools/check-package-fspj-real.py"]),
        run_component("exact-candidate-checkout", [sys.executable, "tools/check-package-exact-candidate-checkout.py", "selftest", "--json"]),
        run_component("claim-port-join", [sys.executable, "tools/compile-claim-port-joins.py", "selftest"]),
        run_component("live-selected-consumers", [sys.executable, "tools/check-live-final-ci-consumers.py", "selftest"]),
        run_component("final-ci-production", [sys.executable, "tools/check-package-final-ci-production.py", "selftest", "--json"]),
        run_component("final-three-surface-role", [sys.executable, "tools/check-package-ci-final-role-demotion.py", "check", "--json"]),
        run_component("contract-modeling-production-migration", [sys.executable, "tools/check-contract-modeling-production-migration.py", "selftest"]),
        run_component("gov-release", [sys.executable, "tools/check-gov-release-integration.py", "selftest", "--json"]),
    ]


def run_selftest() -> dict[str, Any]:
    identity = load_identity()
    components = regression_components()
    failed = [row for row in components if row["status"] != "pass"]
    if failed:
        raise SystemExit(canonical({"kind": "governance.finalScopePurposeJoin.selftest.v8", "status": "fail", "failedComponents": failed}))
    return {
        "kind": "governance.finalScopePurposeJoin.selftest.v8",
        "status": "pass",
        "authority": False,
        "authorityClass": "release-eligibility-evidence",
        "identityProjection": IDENTITY_PATH.relative_to(ROOT).as_posix(),
        "finalCheckName": identity["currentTopology"]["stableCheckName"],
        "currentlyAcceptedDecisionMerge": identity["currentTopology"]["acceptedMerge"],
        "govReleaseDecisionCandidateHead": identity["source"]["head"],
        "govReleaseContractDigest": identity["contract"]["canonicalDigest"],
        "govReleaseAcceptedDecisionDigest": identity["acceptedDecision"]["canonicalDigest"],
        "govReleaseDecisionStatus": identity["source"]["status"],
        "releasePublicationEffect": False,
        "signatureRequired": False,
        "components": components,
        "boundary": "The stable gate proves exact release eligibility only. GitHub merge and CI green do not adopt operational state; only a published canonical gov release manifest plus readback does.",
    }


def run_check(
    candidate_sha: str,
    live_consumers: Path,
    package_contract_scope: Path | None = None,
    package_contract_evidence: Path | None = None,
    expected_ops_candidate: str | None = None,
) -> dict[str, Any]:
    identity = load_identity()
    regression = run_selftest()
    package_member = None
    supplied = [package_contract_scope is not None, package_contract_evidence is not None, expected_ops_candidate is not None]
    if any(supplied) and not all(supplied):
        raise ValueError("package-contract:all-selected-inputs-required")
    if all(supplied):
        package_member = package_contract_closure(package_contract_scope, package_contract_evidence, expected_ops_candidate)

    production = run_component(
        "current-exact-sha-production-evidence",
        [sys.executable, "tools/check-package-final-ci-production.py", "check", "--candidate-sha", candidate_sha, "--live-consumers", str(live_consumers), "--json"],
    )
    if production["status"] != "pass":
        raise SystemExit(canonical({"kind": "governance.finalScopePurposeJoin.gate.v8", "status": "fail", "failedComponents": [production]}))
    parsed = json.loads(production["output"][-1])
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        migration = run_component(
            "contract-modeling-production-cutover",
            [sys.executable, "tools/check-contract-modeling-production-migration.py", "check", "--candidate-sha", candidate_sha, "--out", temporary],
        )
        if migration["status"] != "pass":
            raise SystemExit(canonical({"kind": "governance.finalScopePurposeJoin.gate.v8", "status": "fail", "failedComponents": [migration]}))
        migration_parsed = json.loads((root / "production-migration-candidate.json").read_text(encoding="utf-8"))
        report = {
            "kind": "governance.finalScopePurposeJoin.gate.v8",
            "status": "pass",
            "decision": "allow",
            "authority": False,
            "authorityClass": "release-eligibility-evidence",
            "meaningAuthority": False,
            "effectAuthority": False,
            "companyAdoptionEffect": False,
            "identityProjection": IDENTITY_PATH.relative_to(ROOT).as_posix(),
            "finalCheckName": identity["currentTopology"]["stableCheckName"],
            "candidateSha": candidate_sha,
            "selectedRepositoryCount": parsed["selectedRepositoryCount"],
            "liveConsumerReadback": parsed["liveConsumerReadback"],
            "artifactBodiesVerified": parsed["artifactBodiesVerified"],
            "receiptCandidateShaBound": parsed["receiptCandidateShaBound"],
            "candidateEvidencePass": True,
            "contractModelingAcceptedMerge": migration_parsed["acceptedDecisionMerge"],
            "contractModelingAntiReintroduction": migration_parsed["antiReintroduction"],
            "contractModelingProductionCutoverEligible": migration_parsed["productionCutoverEligible"],
            "govReleaseDecisionCandidateHead": identity["source"]["head"],
            "govReleaseContractDigest": identity["contract"]["canonicalDigest"],
            "govReleaseAcceptedDecisionDigest": identity["acceptedDecision"]["canonicalDigest"],
            "githubMergeHasCompanyAuthority": False,
            "unreleasedCommitHasEffect": False,
            "signatureRequired": False,
            "allRepositoriesEnforced": False,
            "regression": regression,
            "production": parsed,
            "contractModelingMigration": migration_parsed,
        }
        if package_member is not None:
            report["packageContractClosure"] = package_member
        gate_path = root / "gate.json"
        eligibility_path = root / "gov-release-eligibility.json"
        gate_path.write_text(canonical(report) + "\n", encoding="utf-8")
        release = run_component(
            "gov-release-eligibility",
            [sys.executable, "tools/check-gov-release-integration.py", "eligibility", "--gate", str(gate_path), "--live-consumers", str(live_consumers), "--candidate-sha", candidate_sha, "--out", str(eligibility_path)],
        )
        if release["status"] != "pass":
            raise SystemExit(canonical({"kind": "governance.finalScopePurposeJoin.gate.v8", "status": "fail", "failedComponents": [release]}))
        report["govReleaseEligibility"] = json.loads(eligibility_path.read_text(encoding="utf-8"))
        report["releasePublished"] = False
        report["operationalAdoptionEffect"] = False
        report["boundary"] = "The exact candidate is eligible to be evaluated by gov-release. GitHub merge and this green gate do not change operationally adopted state."
        return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=["selftest", "check"], default="selftest")
    parser.add_argument("--candidate-sha")
    parser.add_argument("--live-consumers", type=Path)
    parser.add_argument("--package-contract-scope", type=Path)
    parser.add_argument("--package-contract-evidence", type=Path)
    parser.add_argument("--expected-ops-candidate")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "check":
        if not args.candidate_sha or args.live_consumers is None:
            parser.error("check requires --candidate-sha and --live-consumers")
        report = run_check(
            args.candidate_sha,
            args.live_consumers,
            args.package_contract_scope,
            args.package_contract_evidence,
            args.expected_ops_candidate,
        )
    else:
        if any((args.package_contract_scope, args.package_contract_evidence, args.expected_ops_candidate)):
            parser.error("package-contract inputs are valid only with check")
        report = run_selftest()
    print(canonical(report) if args.json else f"final-scope-purpose-join:{report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
