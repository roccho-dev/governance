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
PACKAGE_MEMBER_KIND = "governance.packageContractClosureMember.v3"
PACKAGE_BUNDLE_CHECKER = ROOT / "tools/check-package-contract-closure-bundle.py"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def package_need(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError("package-contract:" + code)


def package_contract_closure(
    scope_path: Path, evidence_path: Path, expected_target_candidate: str
) -> dict[str, Any]:
    del scope_path, evidence_path, expected_target_candidate
    raise ValueError("package-contract:raw-selected-inputs-not-evidence-bound")


def load_bundle_checker() -> Any:
    spec = importlib.util.spec_from_file_location(
        "contract632_bundle_checker", PACKAGE_BUNDLE_CHECKER
    )
    package_need(
        spec is not None and spec.loader is not None, "bundle-checker-import"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_package_member(
    member: dict[str, Any],
    binding: dict[str, Any],
    target_id: str,
    expected_target_candidate: str,
    expected_negative: dict[str, str],
    status_exit: dict[str, int],
) -> dict[str, Any]:
    package_need(member.get("kind") == PACKAGE_MEMBER_KIND, "member-kind")
    package_need(
        member.get("status") == "pass" and member.get("remaining") == 0,
        "member-status",
    )
    package_need(
        member.get("authority") is False and member.get("adoption") is False,
        "member-authority",
    )
    package_need(
        member.get("releasePublished") is False
        and member.get("claimCeiling") == binding["claimCeiling"],
        "member-boundary",
    )
    package_need(
        member.get("obligationId") == binding["obligationId"],
        "member-obligation",
    )
    package_need(member.get("targetId") == target_id, "member-target-id")
    package_need(
        member.get("targetCandidate") == expected_target_candidate,
        "member-candidate",
    )
    package_need(
        member.get("evidenceBound") is True
        and member.get("sourceBytesVerified")
        == binding["expectedSourceBytesVerified"],
        "member-evidence",
    )
    package_need(
        member.get("receiptReplayed") is True
        and member.get("comparatorReplayed") is True,
        "member-replay",
    )
    package_need(
        member.get("contractDiffStatus") == "CLOSED"
        and member.get("contractDiffExit") == status_exit["CLOSED"],
        "member-positive",
    )
    package_need(
        member.get("negativeStatus") == expected_negative,
        "member-negative-status",
    )
    package_need(
        member.get("negativeExit")
        == {name: status_exit[status] for name, status in expected_negative.items()},
        "member-negative-exit",
    )
    claimed = member.get("memberDigest")
    without_digest = {
        key: value for key, value in member.items() if key != "memberDigest"
    }
    actual = "sha256:" + hashlib.sha256(
        canonical(without_digest).encode()
    ).hexdigest()
    package_need(claimed == actual, "member-digest")
    return member


def package_contract_bundle_closure(
    bundle: Path,
    target_source: Path,
    accepted_requirement_source: Path,
    governance_policy_source: Path,
    target_id: str,
    expected_target_candidate: str,
) -> dict[str, Any]:
    package_need(
        HEX40.fullmatch(expected_target_candidate) is not None,
        "expected-target-candidate",
    )
    module = load_bundle_checker()
    _, binding, _ = module.load_target(target_id)
    member = module.verify_bundle(
        bundle,
        target_source,
        expected_target_candidate,
        accepted_requirement_source,
        target_id,
        None,
        governance_policy_source,
    )
    target_module = module.load_target(target_id)[0]
    return validate_package_member(
        member,
        binding,
        target_id,
        expected_target_candidate,
        target_module.EXPECTED_NEGATIVE,
        module.STATUS_EXIT,
    )


def run_component(name: str, args: list[str]) -> dict[str, Any]:
    process = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "name": name,
        "status": "pass" if process.returncode == 0 else "fail",
        "exitCode": process.returncode,
        "output": process.stdout.strip().splitlines()[-5:],
    }


def regression_components() -> list[dict[str, Any]]:
    return [
        run_component(
            "package-closure-strict",
            [
                sys.executable,
                "tools/check-package-closure-strict.py",
                "selftest",
                "--json",
            ],
        ),
        run_component(
            "required-repo-org-join",
            [
                sys.executable,
                "tools/check-package-required-repo-org-join.py",
                "selftest",
            ],
        ),
        run_component(
            "provider-ci-yaml",
            [sys.executable, "tools/check-provider-ci-yaml.py", "selftest"],
        ),
        run_component(
            "merge-write-boundary-final-gate",
            [
                sys.executable,
                "tools/check-merge-write-boundary-final-gate.py",
                "selftest",
                "--json",
            ],
        ),
        run_component(
            "fspj-real-join",
            [sys.executable, "tools/check-package-fspj-real.py"],
        ),
        run_component(
            "exact-candidate-checkout",
            [
                sys.executable,
                "tools/check-package-exact-candidate-checkout.py",
                "selftest",
                "--json",
            ],
        ),
        run_component(
            "claim-port-join",
            [sys.executable, "tools/compile-claim-port-joins.py", "selftest"],
        ),
        run_component(
            "live-selected-consumers",
            [sys.executable, "tools/check-live-final-ci-consumers.py", "selftest"],
        ),
        run_component(
            "final-ci-production",
            [
                sys.executable,
                "tools/check-package-final-ci-production.py",
                "selftest",
                "--json",
            ],
        ),
        run_component(
            "final-three-surface-role",
            [
                sys.executable,
                "tools/check-package-ci-final-role-demotion.py",
                "check",
                "--json",
            ],
        ),
        run_component(
            "contract-modeling-production-migration",
            [
                sys.executable,
                "tools/check-contract-modeling-production-migration.py",
                "selftest",
            ],
        ),
        run_component(
            "gov-release",
            [
                sys.executable,
                "tools/check-gov-release-integration.py",
                "selftest",
                "--json",
            ],
        ),
    ]


def run_selftest() -> dict[str, Any]:
    identity = load_identity()
    components = regression_components()
    failed = [row for row in components if row["status"] != "pass"]
    if failed:
        raise SystemExit(
            canonical(
                {
                    "kind": "governance.finalScopePurposeJoin.selftest.v8",
                    "status": "fail",
                    "failedComponents": failed,
                }
            )
        )
    return {
        "kind": "governance.finalScopePurposeJoin.selftest.v8",
        "status": "pass",
        "authority": False,
        "authorityClass": "release-eligibility-evidence",
        "identityProjection": IDENTITY_PATH.relative_to(ROOT).as_posix(),
        "finalCheckName": identity["currentTopology"]["stableCheckName"],
        "currentlyAcceptedDecisionMerge": identity["currentTopology"][
            "acceptedMerge"
        ],
        "govReleaseDecisionCandidateHead": identity["source"]["head"],
        "govReleaseContractDigest": identity["contract"]["canonicalDigest"],
        "govReleaseAcceptedDecisionDigest": identity["acceptedDecision"][
            "canonicalDigest"
        ],
        "govReleaseDecisionStatus": identity["source"]["status"],
        "releasePublicationEffect": False,
        "signatureRequired": False,
        "components": components,
        "boundary": (
            "The stable gate proves exact release eligibility only. GitHub merge "
            "and CI green do not adopt operational state; only a published "
            "canonical gov release manifest plus readback does."
        ),
    }


def run_check(
    candidate_sha: str,
    live_consumers: Path,
    package_contract_bundle: Path | None = None,
    package_contract_target_source: Path | None = None,
    package_contract_accepted_requirement_source: Path | None = None,
    package_contract_governance_policy_source: Path | None = None,
    package_contract_target_id: str | None = None,
    expected_target_candidate: str | None = None,
) -> dict[str, Any]:
    package_member = None
    supplied = [
        package_contract_bundle is not None,
        package_contract_target_source is not None,
        package_contract_accepted_requirement_source is not None,
        package_contract_governance_policy_source is not None,
        package_contract_target_id is not None,
        expected_target_candidate is not None,
    ]
    if any(supplied) and not all(supplied):
        raise ValueError("package-contract:all-bundle-inputs-required")
    if all(supplied):
        package_member = package_contract_bundle_closure(
            package_contract_bundle,
            package_contract_target_source,
            package_contract_accepted_requirement_source,
            package_contract_governance_policy_source,
            package_contract_target_id,
            expected_target_candidate,
        )

    identity = load_identity()
    regression = run_selftest()
    production = run_component(
        "current-exact-sha-production-evidence",
        [
            sys.executable,
            "tools/check-package-final-ci-production.py",
            "check",
            "--candidate-sha",
            candidate_sha,
            "--live-consumers",
            str(live_consumers),
            "--json",
        ],
    )
    if production["status"] != "pass":
        raise SystemExit(
            canonical(
                {
                    "kind": "governance.finalScopePurposeJoin.gate.v8",
                    "status": "fail",
                    "failedComponents": [production],
                }
            )
        )
    parsed = json.loads(production["output"][-1])
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        migration = run_component(
            "contract-modeling-production-cutover",
            [
                sys.executable,
                "tools/check-contract-modeling-production-migration.py",
                "check",
                "--candidate-sha",
                candidate_sha,
                "--out",
                temporary,
            ],
        )
        if migration["status"] != "pass":
            raise SystemExit(
                canonical(
                    {
                        "kind": "governance.finalScopePurposeJoin.gate.v8",
                        "status": "fail",
                        "failedComponents": [migration],
                    }
                )
            )
        migration_parsed = json.loads(
            (root / "production-migration-candidate.json").read_text(
                encoding="utf-8"
            )
        )
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
            "contractModelingAcceptedMerge": migration_parsed[
                "acceptedDecisionMerge"
            ],
            "contractModelingAntiReintroduction": migration_parsed[
                "antiReintroduction"
            ],
            "contractModelingProductionCutoverEligible": migration_parsed[
                "productionCutoverEligible"
            ],
            "govReleaseDecisionCandidateHead": identity["source"]["head"],
            "govReleaseContractDigest": identity["contract"]["canonicalDigest"],
            "govReleaseAcceptedDecisionDigest": identity["acceptedDecision"][
                "canonicalDigest"
            ],
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
            report["packageContractClosureDigest"] = package_member[
                "memberDigest"
            ]
        gate_path = root / "gate.json"
        eligibility_path = root / "gov-release-eligibility.json"
        gate_path.write_text(canonical(report) + "\n", encoding="utf-8")
        release = run_component(
            "gov-release-eligibility",
            [
                sys.executable,
                "tools/check-gov-release-integration.py",
                "eligibility",
                "--gate",
                str(gate_path),
                "--live-consumers",
                str(live_consumers),
                "--candidate-sha",
                candidate_sha,
                "--out",
                str(eligibility_path),
            ],
        )
        if release["status"] != "pass":
            raise SystemExit(
                canonical(
                    {
                        "kind": "governance.finalScopePurposeJoin.gate.v8",
                        "status": "fail",
                        "failedComponents": [release],
                    }
                )
            )
        report["govReleaseEligibility"] = json.loads(
            eligibility_path.read_text(encoding="utf-8")
        )
        report["releasePublished"] = False
        report["operationalAdoptionEffect"] = False
        report["boundary"] = (
            "The exact candidate is eligible to be evaluated by gov-release. "
            "GitHub merge and this green gate do not change operationally "
            "adopted state."
        )
        return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", nargs="?", choices=["selftest", "check"], default="selftest"
    )
    parser.add_argument("--candidate-sha")
    parser.add_argument("--live-consumers", type=Path)
    parser.add_argument("--package-contract-bundle", type=Path)
    parser.add_argument("--package-contract-target-source", type=Path)
    parser.add_argument(
        "--package-contract-accepted-requirement-source", type=Path
    )
    parser.add_argument(
        "--package-contract-governance-policy-source", type=Path
    )
    parser.add_argument("--package-contract-target-id")
    parser.add_argument("--expected-target-candidate")
    parser.add_argument("--package-contract-scope", type=Path)
    parser.add_argument("--package-contract-evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if (
        args.package_contract_scope is not None
        or args.package_contract_evidence is not None
    ):
        parser.error(
            "raw package-contract scope/evidence are not evidence-bound; "
            "use --package-contract-bundle"
        )
    if args.command == "check":
        if not args.candidate_sha or args.live_consumers is None:
            parser.error("check requires --candidate-sha and --live-consumers")
        report = run_check(
            args.candidate_sha,
            args.live_consumers,
            args.package_contract_bundle,
            args.package_contract_target_source,
            args.package_contract_accepted_requirement_source,
            args.package_contract_governance_policy_source,
            args.package_contract_target_id,
            args.expected_target_candidate,
        )
    else:
        package_inputs = (
            args.package_contract_bundle,
            args.package_contract_target_source,
            args.package_contract_accepted_requirement_source,
            args.package_contract_governance_policy_source,
            args.package_contract_target_id,
            args.expected_target_candidate,
        )
        if any(package_inputs):
            parser.error(
                "package-contract inputs are valid only with check"
            )
        report = run_selftest()
    print(
        canonical(report)
        if args.json
        else f"final-scope-purpose-join:{report['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
