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
FINAL_CHECK_NAME = "gov-final-scope-purpose-join / gate"


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def run_component(name: str, args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {
        "name": name,
        "status": "pass" if proc.returncode == 0 else "fail",
        "exitCode": proc.returncode,
        "output": proc.stdout.strip().splitlines()[-5:],
    }


def regression_components() -> list[dict[str, Any]]:
    return [
        run_component(
            "package-closure-strict",
            [sys.executable, "tools/check-package-closure-strict.py", "selftest", "--json"],
        ),
        run_component(
            "required-repo-org-join",
            [sys.executable, "tools/check-package-required-repo-org-join.py", "selftest"],
        ),
        run_component(
            "provider-ci-yaml",
            [sys.executable, "tools/check-provider-ci-yaml.py", "selftest"],
        ),
        run_component(
            "merge-write-boundary-final-gate",
            [sys.executable, "tools/check-merge-write-boundary-final-gate.py", "selftest", "--json"],
        ),
        run_component("fspj-real-join", [sys.executable, "tools/check-package-fspj-real.py"]),
        run_component(
            "exact-candidate-checkout",
            [sys.executable, "tools/check-package-exact-candidate-checkout.py", "selftest", "--json"],
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
            [sys.executable, "tools/check-package-final-ci-production.py", "selftest", "--json"],
        ),
        run_component(
            "final-two-surface-role",
            [sys.executable, "tools/check-package-ci-final-role-demotion.py", "check", "--json"],
        ),
        run_component(
            "contract-modeling-production-migration",
            [sys.executable, "tools/check-contract-modeling-production-migration.py", "selftest"],
        ),
    ]


def run_selftest() -> dict[str, Any]:
    components = regression_components()
    failed = [row for row in components if row["status"] != "pass"]
    if failed:
        raise SystemExit(
            canonical(
                {
                    "kind": "governance.finalScopePurposeJoin.selftest.v4",
                    "status": "fail",
                    "failedComponents": failed,
                }
            )
        )
    return {
        "kind": "governance.finalScopePurposeJoin.selftest.v4",
        "status": "pass",
        "authority": False,
        "authorityClass": "evidence-only",
        "finalCheckName": FINAL_CHECK_NAME,
        "acceptedDecisionMerge": "a8fc9e8e04d53f1d783317059e4421c8dc724d01",
        "contractModelingAcceptedMerge": "458ab4267882083de0593754d1bf9766bf8d54da",
        "components": components,
        "boundary": "Selftests are evidence only. Production admission requires fresh live consumer receipts and production contract-modeling migration closure for the exact candidate.",
    }


def run_check(candidate_sha: str, live_consumers: Path) -> dict[str, Any]:
    regression = run_selftest()
    production = run_component(
        "current-exact-sha-production-admission",
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
                    "kind": "governance.finalScopePurposeJoin.gate.v4",
                    "status": "fail",
                    "failedComponents": [production],
                }
            )
        )
    parsed = json.loads(production["output"][-1])

    with tempfile.TemporaryDirectory() as temporary:
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
                        "kind": "governance.finalScopePurposeJoin.gate.v4",
                        "status": "fail",
                        "failedComponents": [migration],
                    }
                )
            )
        migration_parsed = json.loads(
            (Path(temporary) / "production-migration-candidate.json").read_text(encoding="utf-8")
        )

    return {
        "kind": "governance.finalScopePurposeJoin.gate.v4",
        "status": "pass",
        "decision": "allow",
        "authority": True,
        "authorityClass": "merge-admission",
        "meaningAuthority": False,
        "effectAuthority": False,
        "finalCheckName": FINAL_CHECK_NAME,
        "candidateSha": candidate_sha,
        "acceptedDecisionMerge": parsed["acceptedDecisionMerge"],
        "selectedRepositoryCount": parsed["selectedRepositoryCount"],
        "liveConsumerReadback": parsed["liveConsumerReadback"],
        "artifactBodiesVerified": parsed["artifactBodiesVerified"],
        "receiptCandidateShaBound": parsed["receiptCandidateShaBound"],
        "productionAdmission": True,
        "contractModelingAcceptedMerge": migration_parsed["acceptedDecisionMerge"],
        "contractModelingLegacyResponsibilityCount": migration_parsed["legacyResponsibilityCount"],
        "contractModelingLegacyConsumerCount": migration_parsed["legacyActiveConsumerCount"],
        "contractModelingAntiReintroduction": migration_parsed["antiReintroduction"],
        "contractModelingProductionCutoverEligible": migration_parsed["productionCutoverEligible"],
        "contractModelingEffectReadbackRequired": migration_parsed["effectReadbackRequired"],
        "contractModelingMigrationCompleteCandidate": migration_parsed["migrationCompleteAfterEffectReadback"],
        "allRepositoriesEnforced": False,
        "regression": regression,
        "production": parsed,
        "contractModelingMigration": migration_parsed,
        "boundary": "Allows only the exact governance candidate after live UI/Ops readback and complete contract-modeling production-cutover proof. Migration completion becomes true only after merge effect readback.",
    }


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
