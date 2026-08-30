#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gov_release.identity import IDENTITY_PATH, load_identity  # noqa: E402


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
        run_component("package-obligation-execution-join", [sys.executable, "tools/check-package-obligation-execution-join.py", "selftest", "--json"]),
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


def run_check(candidate_sha: str, live_consumers: Path) -> dict[str, Any]:
    identity = load_identity()
    regression = run_selftest()
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
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "check":
        if not args.candidate_sha or args.live_consumers is None:
            parser.error("check requires --candidate-sha and --live-consumers")
        report = run_check(args.candidate_sha, args.live_consumers)
    else:
        report = run_selftest()
    print(canonical(report) if args.json else f"final-scope-purpose-join:{report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
