#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
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
MEMBER_KIND = "governance.packageContractClosureMember.v3"
BUNDLE_CHECKER = ROOT / "tools/check-package-contract-closure-bundle.py"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("package-contract:" + code)


def load_checker() -> Any:
    spec = importlib.util.spec_from_file_location("contract632_bundle_checker", BUNDLE_CHECKER)
    need(spec is not None and spec.loader is not None, "bundle-checker-import")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_component(name: str, args: list[str]) -> dict[str, Any]:
    process = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {
        "name": name,
        "status": "pass" if process.returncode == 0 else "fail",
        "exitCode": process.returncode,
        "output": process.stdout.strip().splitlines()[-5:],
    }


def regression_components() -> list[dict[str, Any]]:
    commands = [
        ("package-closure-strict", [sys.executable, "tools/check-package-closure-strict.py", "selftest", "--json"]),
        ("required-repo-org-join", [sys.executable, "tools/check-package-required-repo-org-join.py", "selftest"]),
        ("provider-ci-yaml", [sys.executable, "tools/check-provider-ci-yaml.py", "selftest"]),
        ("merge-write-boundary-final-gate", [sys.executable, "tools/check-merge-write-boundary-final-gate.py", "selftest", "--json"]),
        ("fspj-real-join", [sys.executable, "tools/check-package-fspj-real.py"]),
        ("exact-candidate-checkout", [sys.executable, "tools/check-package-exact-candidate-checkout.py", "selftest", "--json"]),
        ("claim-port-join", [sys.executable, "tools/compile-claim-port-joins.py", "selftest"]),
        ("live-selected-consumers", [sys.executable, "tools/check-live-final-ci-consumers.py", "selftest"]),
        ("final-ci-production", [sys.executable, "tools/check-package-final-ci-production.py", "selftest", "--json"]),
        ("final-three-surface-role", [sys.executable, "tools/check-package-ci-final-role-demotion.py", "check", "--json"]),
        ("contract-modeling-production-migration", [sys.executable, "tools/check-contract-modeling-production-migration.py", "selftest"]),
        ("gov-release", [sys.executable, "tools/check-gov-release-integration.py", "selftest", "--json"]),
    ]
    return [run_component(name, command) for name, command in commands]


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


def validate_member(
    member: dict[str, Any],
    binding: dict[str, Any],
    target_id: str,
    target_candidate: str,
    governance_candidate: str,
    checker: Any,
) -> dict[str, Any]:
    need(member.get("kind") == MEMBER_KIND, "member-kind")
    need(member.get("status") == "pass" and member.get("remaining") == 0, "member-status")
    need(member.get("authority") is False and member.get("adoption") is False, "member-authority")
    need(member.get("releasePublished") is False and member.get("claimCeiling") == binding["claimCeiling"], "member-boundary")
    need(member.get("targetId") == target_id and member.get("obligationId") == binding["obligationId"], "member-identity")
    need(member.get("targetCandidate") == target_candidate, "member-target-candidate")
    need(member.get("governanceCandidate") == governance_candidate, "member-governance-candidate")
    need(member.get("evidenceBound") is True and member.get("sourceBytesVerified") == binding["expectedSourceBytesVerified"], "member-evidence")
    need(member.get("receiptReplayed") is True and member.get("comparatorReplayed") is True, "member-replay")
    need(member.get("contractDiffStatus") == "CLOSED" and member.get("contractDiffExit") == checker.STATUS_EXIT["CLOSED"], "member-positive")
    need(member.get("negativeStatus") == checker.REQUIRED_NEGATIVE, "member-negative-status")
    need(member.get("negativeExit") == {name: checker.STATUS_EXIT[status] for name, status in checker.REQUIRED_NEGATIVE.items()}, "member-negative-exit")
    claimed = member.get("memberDigest")
    raw = {key: value for key, value in member.items() if key != "memberDigest"}
    actual = "sha256:" + hashlib.sha256(canonical(raw).encode()).hexdigest()
    need(claimed == actual, "member-digest")
    return member


def package_member(
    candidate_sha: str,
    bundle: Path,
    target_source: Path,
    accepted_source: Path,
    policy_source: Path,
    target_id: str,
    target_candidate: str,
) -> dict[str, Any]:
    need(HEX40.fullmatch(candidate_sha) is not None, "governance-candidate")
    need(HEX40.fullmatch(target_candidate) is not None, "target-candidate")
    checker = load_checker()
    _, binding, _ = checker.load_target(target_id)
    member = checker.verify_bundle(
        bundle,
        target_source,
        target_candidate,
        accepted_source,
        target_id,
        candidate_sha,
        policy_source,
    )
    return validate_member(member, binding, target_id, target_candidate, candidate_sha, checker)


def run_package_check(args: argparse.Namespace) -> dict[str, Any]:
    member = package_member(
        args.candidate_sha,
        args.package_contract_bundle,
        args.package_contract_target_source,
        args.package_contract_accepted_requirement_source,
        args.package_contract_governance_policy_source,
        args.package_contract_target_id,
        args.expected_target_candidate,
    )
    return {
        "kind": "governance.finalScopePurposeJoin.package.v1",
        "status": "pass",
        "authority": False,
        "adoption": False,
        "releasePublished": False,
        "candidateSha": args.candidate_sha,
        "packageContractClosure": member,
        "packageContractClosureDigest": member["memberDigest"],
        "remaining": 0,
    }


def run_check(args: argparse.Namespace) -> dict[str, Any]:
    member = None
    supplied = [
        args.package_contract_bundle,
        args.package_contract_target_source,
        args.package_contract_accepted_requirement_source,
        args.package_contract_governance_policy_source,
        args.package_contract_target_id,
        args.expected_target_candidate,
    ]
    if any(value is not None for value in supplied):
        need(all(value is not None for value in supplied), "all-bundle-inputs-required")
        member = package_member(
            args.candidate_sha,
            args.package_contract_bundle,
            args.package_contract_target_source,
            args.package_contract_accepted_requirement_source,
            args.package_contract_governance_policy_source,
            args.package_contract_target_id,
            args.expected_target_candidate,
        )

    identity = load_identity()
    regression = run_selftest()
    production = run_component("current-exact-sha-production-evidence", [
        sys.executable,
        "tools/check-package-final-ci-production.py",
        "check",
        "--candidate-sha",
        args.candidate_sha,
        "--live-consumers",
        str(args.live_consumers),
        "--json",
    ])
    if production["status"] != "pass":
        raise SystemExit(canonical({"kind": "governance.finalScopePurposeJoin.gate.v8", "status": "fail", "failedComponents": [production]}))
    parsed = json.loads(production["output"][-1])
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        migration = run_component("contract-modeling-production-cutover", [
            sys.executable,
            "tools/check-contract-modeling-production-migration.py",
            "check",
            "--candidate-sha",
            args.candidate_sha,
            "--out",
            temporary,
        ])
        if migration["status"] != "pass":
            raise SystemExit(canonical({"kind": "governance.finalScopePurposeJoin.gate.v8", "status": "fail", "failedComponents": [migration]}))
        migration_value = json.loads((root / "production-migration-candidate.json").read_text(encoding="utf-8"))
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
            "candidateSha": args.candidate_sha,
            "selectedRepositoryCount": parsed["selectedRepositoryCount"],
            "liveConsumerReadback": parsed["liveConsumerReadback"],
            "artifactBodiesVerified": parsed["artifactBodiesVerified"],
            "receiptCandidateShaBound": parsed["receiptCandidateShaBound"],
            "candidateEvidencePass": True,
            "contractModelingAcceptedMerge": migration_value["acceptedDecisionMerge"],
            "contractModelingAntiReintroduction": migration_value["antiReintroduction"],
            "contractModelingProductionCutoverEligible": migration_value["productionCutoverEligible"],
            "govReleaseDecisionCandidateHead": identity["source"]["head"],
            "govReleaseContractDigest": identity["contract"]["canonicalDigest"],
            "govReleaseAcceptedDecisionDigest": identity["acceptedDecision"]["canonicalDigest"],
            "githubMergeHasCompanyAuthority": False,
            "unreleasedCommitHasEffect": False,
            "signatureRequired": False,
            "allRepositoriesEnforced": False,
            "regression": regression,
            "production": parsed,
            "contractModelingMigration": migration_value,
        }
        if member is not None:
            report["packageContractClosure"] = member
            report["packageContractClosureDigest"] = member["memberDigest"]
        gate_path = root / "gate.json"
        eligibility_path = root / "gov-release-eligibility.json"
        gate_path.write_text(canonical(report) + "\n", encoding="utf-8")
        release = run_component("gov-release-eligibility", [
            sys.executable,
            "tools/check-gov-release-integration.py",
            "eligibility",
            "--gate",
            str(gate_path),
            "--live-consumers",
            str(args.live_consumers),
            "--candidate-sha",
            args.candidate_sha,
            "--out",
            str(eligibility_path),
        ])
        if release["status"] != "pass":
            raise SystemExit(canonical({"kind": "governance.finalScopePurposeJoin.gate.v8", "status": "fail", "failedComponents": [release]}))
        report["govReleaseEligibility"] = json.loads(eligibility_path.read_text(encoding="utf-8"))
        report["releasePublished"] = False
        report["operationalAdoptionEffect"] = False
        report["boundary"] = "The exact candidate is eligible to be evaluated by gov-release. GitHub merge and this green gate do not change operationally adopted state."
        return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", choices=["selftest", "check", "check-package"], default="selftest")
    parser.add_argument("--candidate-sha")
    parser.add_argument("--live-consumers", type=Path)
    parser.add_argument("--package-contract-bundle", type=Path)
    parser.add_argument("--package-contract-target-source", type=Path)
    parser.add_argument("--package-contract-accepted-requirement-source", type=Path)
    parser.add_argument("--package-contract-governance-policy-source", type=Path)
    parser.add_argument("--package-contract-target-id")
    parser.add_argument("--expected-target-candidate")
    parser.add_argument("--package-contract-scope", type=Path)
    parser.add_argument("--package-contract-evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.package_contract_scope is not None or args.package_contract_evidence is not None:
        parser.error("raw package-contract scope/evidence are not evidence-bound; use --package-contract-bundle")
    package_values = [
        args.package_contract_bundle,
        args.package_contract_target_source,
        args.package_contract_accepted_requirement_source,
        args.package_contract_governance_policy_source,
        args.package_contract_target_id,
        args.expected_target_candidate,
    ]
    if args.command == "selftest":
        if args.candidate_sha or args.live_consumers is not None or any(package_values):
            parser.error("selftest accepts no candidate inputs")
        report = run_selftest()
    elif args.command == "check-package":
        if not args.candidate_sha or not all(package_values) or args.live_consumers is not None:
            parser.error("check-package requires candidate and all package inputs only")
        report = run_package_check(args)
    else:
        if not args.candidate_sha or args.live_consumers is None:
            parser.error("check requires --candidate-sha and --live-consumers")
        report = run_check(args)
    print(canonical(report) if args.json else f"final-scope-purpose-join:{report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
